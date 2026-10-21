"""LLM サーバーの起動 (モデルのロード) にかかる時間を、ページキャッシュの有無で比べる。

サーバーの起動・停止は local-llm-bench のスクリプト (strata.sh / llamacpp.sh) に任せる。
1回の計測で記録するもの:
  ready_s   コンテナ起動から /health (または /v1/models) が 200 を返すまでの秒数
  first_s   ready の後、最初の短いリクエスト (max_tokens=8) が返るまでの秒数
            (mmap はページを触るまで読まないので、ロードの残りがここに出る)
  total_s   ready_s + first_s (= 使い始められるまでの時間)
  disk_gb   その間にストレージ (RAID0 の3台) から読んだ量
cold はページキャッシュを捨ててから起動 (sudo -n が使えれば drop_caches、使えなければ対象ファイルだけ fadvise で)、warm は直前の読み込みが残った状態。

usage: uv run python scripts/model_load.py --label model-load [--only strata] [--cold 3] [--warm 1]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

console = Console()
log = logging.getLogger("model-load")

REPO = Path(__file__).resolve().parents[1]
LLM_BENCH = Path.home() / "ghq/github.com/akivajp/local-llm-bench/scripts"
GGUF_IQ3S = "Qwen3.8-Flash-Next-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"
# ルートの btrfs を構成するデバイス (nvme0n1 等)。再起動で番号が入れ替わることがあるので、毎回 sysfs から取る
RAID_DEVS = {d.name for d in Path("/sys/fs/btrfs").glob("*/devices/*")
             if Path("/sys/fs/btrfs", d.parent.parent.name, "devices").is_dir()}


@dataclass
class Server:
    """計測するサーバーの構成。"""

    name: str
    up: list[str]  # 起動コマンド
    down: list[str]  # 停止コマンド
    url: str
    env: dict[str, str] = field(default_factory=dict)


def servers() -> list[Server]:
    """計測する構成の一覧 (Strata が本命。llama.cpp はロード方法の違いを見る)。"""
    strata_env = {"STRATA_MODEL": "IQ3_S", "STRATA_VARIANT": "upstream"}
    lc = [str(LLM_BENCH / "llamacpp.sh"), "up", GGUF_IQ3S, "-sm", "layer"]
    lc_down = [str(LLM_BENCH / "llamacpp.sh"), "down"]
    return [
        Server("strata-iq3s-4090", [str(LLM_BENCH / "strata.sh"), "up", "GPU=0"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", strata_env),
        # 読み込みのスレッドを 16 本以上にする (Strata の既定では Windows 以外は常にバッファ読み込みで、スレッドは最大 6)
        Server("strata-iq3s-4090-unbuf", [str(LLM_BENCH / "strata.sh"), "up", "GPU=0", "STRATA_UNBUFFERED_LOAD=1"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", strata_env),
        # Linux の O_DIRECT 読み込みを足したパッチ版 (llmb-strata:odirect)。データは本家と共有 (docker-data-odirect はリンク)
        Server("strata-odirect-iq3s-4090-direct", [str(LLM_BENCH / "strata.sh"), "up", "GPU=0", "STRATA_UNBUFFERED_LOAD=1"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", {**strata_env, "STRATA_VARIANT": "odirect"}),
        Server("strata-odirect-iq3s-4090-buffered", [str(LLM_BENCH / "strata.sh"), "up", "GPU=0"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", {**strata_env, "STRATA_VARIANT": "odirect"}),
        # 読み込んだ arena のチェックサムを出す (正しさの確認用。全体のハッシュ計算で起動が遅くなるので時間は比べない)
        Server("verify-strata-iq3s-4090", [str(LLM_BENCH / "strata.sh"), "up", "GPU=0", "STRATA_VERIFY_ARENA=1"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", strata_env),
        Server("verify-strata-odirect-iq3s-4090-direct",
               [str(LLM_BENCH / "strata.sh"), "up", "GPU=0", "STRATA_UNBUFFERED_LOAD=1", "STRATA_VERIFY_ARENA=1"],
               [str(LLM_BENCH / "strata.sh"), "down"], "http://127.0.0.1:18080", {**strata_env, "STRATA_VARIANT": "odirect"}),
        Server("llamacpp-iq3s-2gpu-mmap", lc + ["--load-mode", "mmap"], lc_down, "http://127.0.0.1:18081"),
        Server("llamacpp-iq3s-2gpu-none", lc + ["--load-mode", "none"], lc_down, "http://127.0.0.1:18081"),
        Server("llamacpp-iq3s-2gpu-dio", lc + ["--load-mode", "dio"], lc_down, "http://127.0.0.1:18081"),
    ]


# cold の計測で捨てるページキャッシュ (モデルと Strata の変換済みデータ)
CACHE_DIRS = [
    Path.home() / "llm-lab/gguf/Qwen3.8-Flash-Next-GSQ-RCO/IQ3_S",
    Path.home() / "llm-lab/strata/docker-data-upstream",
]


def drop_file_cache(dirs: list[Path]) -> None:
    """指定ディレクトリ以下のファイルのページキャッシュを捨てる (posix_fadvise DONTNEED。root 不要)。

    sudo が使えるなら vm.drop_caches=3 (全体) を使う。使えなければ対象のファイルだけを捨てる。
    """
    if subprocess.run(["sudo", "-n", "sysctl", "-w", "vm.drop_caches=3"], capture_output=True).returncode == 0:
        return
    for d in dirs:
        for f in d.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    fd = os.open(f, os.O_RDONLY)
                except OSError:
                    continue  # コンテナ内の root が作った読めないファイルは対象外 (小さい設定ファイル)
                try:
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                finally:
                    os.close(fd)


def disk_read_bytes() -> int:
    """RAID0 の3台から読み出したバイト数の累計 (/proc/diskstats の6列目は 512 バイト単位)。"""
    total = 0
    with open("/proc/diskstats") as f:
        for line in f:
            cols = line.split()
            if cols[2] in RAID_DEVS:
                total += int(cols[5]) * 512
    return total


class ReadTracer:
    """別スレッドで一定間隔ごとにディスクの読み出し量を記録する (ロード中の読み込み速度の推移を見るため)。"""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self.samples: list[tuple[float, float]] = []  # (経過秒, その区間の読み込み速度 GB/s)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        t0 = prev_t = time.monotonic()
        prev_b = disk_read_bytes()
        while not self._stop.wait(self.interval):
            t, b = time.monotonic(), disk_read_bytes()
            self.samples.append((round(t - t0, 2), round((b - prev_b) / 1e9 / (t - prev_t), 2)))
            prev_t, prev_b = t, b

    def __enter__(self) -> ReadTracer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()


def http_get_ok(url: str) -> bool:
    """GET して 200 なら True。"""
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_ready(base: str, timeout: float) -> float:
    """/health か /v1/models が 200 を返すまで待ち、かかった秒数を返す。"""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if http_get_ok(base + "/health") or http_get_ok(base + "/v1/models"):
            return time.monotonic() - t0
        time.sleep(0.5)
    raise TimeoutError(f"{base} が {timeout} 秒以内に応答しませんでした")


def first_request(base: str) -> float:
    """最初の短いリクエストを送り、返るまでの秒数を返す。"""
    with urllib.request.urlopen(base + "/v1/models", timeout=30) as r:
        model = json.load(r)["data"][0]["id"]
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Say hello."}],
        "max_tokens": 8,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        r.read()
    return time.monotonic() - t0


def run(cmd: list[str], env: dict[str, str]) -> None:
    """補助スクリプトを実行する (失敗したら例外)。"""
    subprocess.run(cmd, check=True, capture_output=True, text=True, env={**os.environ, **env})


def main() -> None:
    """構成 × (cold × N, warm × M) を順に計測し、runs/<label>/model_load.jsonl に保存する。"""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", default="model-load", help="保存先 runs/<label>/ の名前")
    p.add_argument("--only", action="append", help="構成名に含まれる文字列で絞る (複数指定可)")
    p.add_argument("--exact", action="store_true", help="--only を部分一致ではなく完全一致で使う")
    p.add_argument("--cold", type=int, default=3, help="ページキャッシュを捨ててからの計測回数")
    p.add_argument("--warm", type=int, default=1, help="キャッシュが残った状態での計測回数 (cold の後に流す)")
    p.add_argument("--timeout", type=float, default=900, help="起動待ちの上限 (秒)")
    p.add_argument("--trace", action="store_true", help="0.5秒ごとの読み込み速度を記録する (runs/<label>/trace-*.json)")
    args = p.parse_args()

    out = REPO / "runs" / args.label
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True, handlers=[
        RichHandler(console=console, show_path=False),
        _file_handler(out / "model_load.log"),
    ])
    def wanted(name: str) -> bool:
        if not args.only:
            return True
        return name in args.only if args.exact else any(o in name for o in args.only)

    targets = [s for s in servers() if wanted(s.name)]
    rows: list[dict[str, object]] = []
    for s in targets:
        for mode in ["cold"] * args.cold + ["warm"] * args.warm:
            run(s.down, s.env)  # 前の構成が残っていれば止める
            if mode == "cold":
                os.sync()
                drop_file_cache(CACHE_DIRS)
            tracer = ReadTracer()
            if args.trace:
                tracer.__enter__()
            a, t0 = disk_read_bytes(), time.monotonic()
            run(s.up, s.env)
            try:
                ready = wait_ready(s.url, args.timeout)
                first = first_request(s.url)
            finally:
                b = disk_read_bytes()
                if args.trace:
                    tracer.__exit__()
                    stamp = datetime.now().strftime("%H%M%S")
                    (out / f"trace-{s.name}-{mode}-{stamp}.json").write_text(json.dumps(tracer.samples))
                run(s.down, s.env)
            row = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "server": s.name, "mode": mode,
                "ready_s": round(ready, 1), "first_s": round(first, 1), "total_s": round(ready + first, 1),
                "disk_gb": round((b - a) / 1e9, 1), "up": s.up,
            }
            rows.append(row)
            with (out / "model_load.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.info("%s %s: ready %.1f 秒 + 最初の応答 %.1f 秒 = %.1f 秒 (ディスクから %.1f GB)",
                     s.name, mode, ready, first, ready + first, row["disk_gb"])
            if args.trace and tracer.samples:
                peak = max(v for _, v in tracer.samples)
                busy = [t for t, v in tracer.samples if v >= 0.5]  # 0.5GB/s 以上読んでいた区間
                log.info("  読み込みの最大 %.1f GB/s、0.5GB/s 以上読んでいた時間 %.1f〜%.1f 秒",
                         peak, busy[0] if busy else 0, busy[-1] if busy else 0)

    table = Table(title="モデルのロード時間 (秒)")
    for col in ("構成", "条件", "ready", "最初の応答", "合計", "ディスク読み出し"):
        table.add_column(col, justify="left" if col in ("構成", "条件") else "right")
    for r in rows:
        table.add_row(str(r["server"]), str(r["mode"]), f'{r["ready_s"]}', f'{r["first_s"]}', f'{r["total_s"]}', f'{r["disk_gb"]} GB')
    console.print(table)


def _file_handler(path: Path) -> logging.Handler:
    """日時付きでログファイルに書くハンドラ。"""
    h = logging.FileHandler(path, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    return h


if __name__ == "__main__":
    main()
