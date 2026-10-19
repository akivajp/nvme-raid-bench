"""nvme-bench コマンドの入口。

サブコマンド:
  run      設定ファイルの suite を指定した対象で流し、runs/<label>/ に結果を保存する
  compare  複数の runs/<label>/results.jsonl を並べて比較表を出す
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .fio import (
    FioResult,
    Target,
    TestSpec,
    build_command,
    build_precondition_command,
    device_busy_reasons,
    parse_fio_json,
    parse_size,
)
from .monitor import TempMonitor, nvme_hwmon_paths, smart_thermal_all

console = Console()
log = logging.getLogger("nvme-bench")

REPO = Path(__file__).resolve().parents[2]

# 設定ファイルの defaults をコマンドラインで上書きできる項目 (引数名 → 設定キー)
_OVERRIDES = {
    "runtime": "runtime",
    "ramp_time": "ramp_time",
    "repeats": "repeats",
    "size": "size",
    "cooldown": "cooldown",
}


def setup_logging(log_path: Path | None) -> None:
    """コンソール (rich) とログファイルの両方に日時付きで出力する。"""
    handlers: list[logging.Handler] = [RichHandler(console=console, show_path=False)]
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        handlers.append(fh)
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=handlers, force=True)


def load_config(args: argparse.Namespace) -> dict[str, Any]:
    """YAML を読み、コマンドライン引数で defaults を上書きした実効設定を返す。"""
    with open(args.config, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}
    defaults = cfg.setdefault("defaults", {})
    for arg_name, key in _OVERRIDES.items():
        v = getattr(args, arg_name, None)
        if v is not None:
            defaults[key] = v
    return cfg


def make_target(name: str, d: dict[str, Any]) -> Target:
    """設定の targets の1項目から Target を作る (~ を展開する)。"""
    return Target(
        name=name,
        kind=d["kind"],
        path=Path(os.path.expanduser(d["path"])),
        readonly=bool(d.get("readonly", False)),
    )


def target_size(target: Target, default_size: int) -> int:
    """対象の大きさ (バイト)。生デバイスは sysfs から、ファイルは実サイズ (無ければ既定値)。"""
    if target.is_device:
        # /sys/block/<dev>/size は 512 バイト単位 (論理セクタサイズに関係なく)
        return int(Path(f"/sys/block/{target.path.name}/size").read_text()) * 512
    if target.path.exists():
        return target.path.stat().st_size
    return default_size


def run_cmd(cmd: list[str], *, sudo: bool = False, timeout: float | None = None) -> str:
    """コマンドを実行して標準出力を返す。失敗したら標準エラーごと例外にする。"""
    full = (["sudo", "-n"] if sudo else []) + cmd
    proc = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"コマンドが失敗しました ({proc.returncode}): {shlex.join(full)}\n{proc.stderr.strip()}")
    return proc.stdout


def check_destroy_allowed(targets: list[Target], allowed: list[str], writes: bool) -> None:
    """生デバイスへ書き込む前の安全確認。問題があれば理由を表示して終了する。"""
    for t in targets:
        if not t.is_device or not writes:
            continue
        if str(t.path) not in allowed:
            sys.exit(f"{t.path} へ書き込みます (中身は消えます)。意図どおりなら --allow-destroy {t.path} を付けてください")
        reasons = device_busy_reasons(t.path)
        # btrfs のマルチデバイス構成に加えたデバイスはマウント一覧に載らないことがあるため、署名も見る
        fstypes = run_cmd(["lsblk", "-no", "FSTYPE", str(t.path)]).split()
        if fstypes:
            reasons.append(f"ファイルシステムの署名があります ({', '.join(fstypes)})")
        if reasons:
            sys.exit(f"{t.path} には書き込めません: " + " / ".join(reasons))


def prepare_file_target(target: Target, size_bytes: int) -> None:
    """btrfs 上の計測用ファイルを作り直す。置き場所のサブボリュームが無ければ作る。

    RAID0 化の後も計測のたびに作り直すことで、ファイルが新しい構成で配置されることを保証する。
    """
    parent = target.path.parent
    if not parent.exists():
        # snapper のスナップショットに含まれないよう、入れ子のサブボリュームにする (root 不要)
        run_cmd(["btrfs", "subvolume", "create", str(parent)])
        log.info("サブボリュームを作成しました: %s", parent)
    if target.path.exists():
        target.path.unlink()
    log.info("計測用ファイルを作成します: %s (%.1f GiB)", target.path, size_bytes / 1024**3)
    run_cmd(build_precondition_command(target, size_bytes))
    # 書き込み直後の状態を揃えるため、ファイルシステムの書き出しを待つ
    os.sync()


def drop_caches() -> None:
    """ページキャッシュを捨てる (要 sudo)。モデルを初めて読み込むときの状態を再現する。"""
    os.sync()
    run_cmd(["sysctl", "-w", "vm.drop_caches=3"], sudo=True)


def fmt_bw(bw_bytes: float) -> str:
    """帯域を MB/s (10進。CrystalDiskMark と同じ) で表示する。"""
    return f"{bw_bytes / 1e6:,.0f} MB/s"


def run_suite(args: argparse.Namespace) -> None:
    """run サブコマンド: suite を対象ごと (または同時) に流して結果を保存する。"""
    cfg = load_config(args)
    defaults = cfg["defaults"]
    suite = cfg["suites"][args.suite]
    out_dir = REPO / "runs" / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(Path(args.log) if args.log else out_dir / "run.log")

    targets = [make_target(n, cfg["targets"][n]) for n in args.target]
    specs = [TestSpec.from_dict(t, defaults) for t in suite["tests"]]
    # コマンドラインで指定した時間・回数は、test ごとの指定よりも優先する
    # (size は test ごとの範囲 (300g / full 等) に意味があるため、defaults の上書きに留める)
    for key in ("runtime", "ramp_time", "repeats"):
        v = getattr(args, key, None)
        if v is not None:
            for s in specs:
                setattr(s, key, v)
    if args.only:
        specs = [s for s in specs if any(o in s.name for o in args.only)]
    has_writes = any(s.is_write for s in specs) or bool(suite.get("precondition"))
    check_destroy_allowed(targets, args.allow_destroy or [], has_writes)

    # 読み取り専用の対象には書き込みの計測をしない
    def applicable(spec: TestSpec, group: list[Target]) -> bool:
        return not (spec.is_write and any(t.readonly for t in group))

    # 同時計測の suite は全対象を1グループ、そうでなければ対象ごとに1グループ
    groups = [targets] if suite.get("concurrent") else [[t] for t in targets]
    plan = [(g, s, r) for g in groups for s in specs if applicable(s, g) for r in range(s.repeats)]
    if not plan:
        sys.exit("実行する計測がありません (読み取り専用の対象に書き込みの計測だけを指定していないか確認してください)")

    # 実行時の設定を残す (この run で使う対象と suite の分だけ)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    effective = {
        "argv": sys.argv,
        "defaults": defaults,
        "suite": {args.suite: suite},
        "targets": {t.name: cfg["targets"][t.name] for t in targets},
    }
    (out_dir / f"config-{args.suite}-{stamp}.yaml").write_text(yaml.safe_dump(effective, allow_unicode=True, sort_keys=False))
    log.info("設定: suite=%s 対象=%s defaults=%s", args.suite, [t.name for t in targets], defaults)

    # 計測環境の記録 (初回のみ。RAID 化の前後でラベルを分ければ、それぞれに残る)
    env_md = out_dir / "env.md"
    if not env_md.exists() and not args.no_env:
        log.info("計測環境を記録します: %s", env_md)
        env_md.write_text(run_cmd([str(REPO / "scripts" / "collect-env.sh")], timeout=120))

    ctrls = sorted(nvme_hwmon_paths())
    need_sudo = any(t.is_device for t in targets)
    default_size = parse_size(defaults["size"])
    (out_dir / "fio").mkdir(exist_ok=True)
    (out_dir / "temps").mkdir(exist_ok=True)

    # 前処理: 生デバイスの TRIM、計測範囲の書き埋め、計測用ファイルの作り直し
    for t in targets:
        if t.is_device and suite.get("pre_discard"):
            log.info("%s を TRIM します (SLC キャッシュを空きの多い状態に戻す)", t.path)
            run_cmd(["blkdiscard", "-f", str(t.path)], sudo=True, timeout=600)
            idle = int(suite.get("pre_idle", 60))
            log.info("TRIM 後に %d 秒待ちます", idle)
            time.sleep(idle)
        if not suite.get("precondition") or args.no_precondition:
            continue
        if t.kind == "file" and not t.readonly:
            prepare_file_target(t, default_size)
        elif t.is_device:
            log.info("%s の先頭 %.1f GiB を書き埋めます", t.path, default_size / 1024**3)
            run_cmd(build_precondition_command(t, default_size), sudo=True)

    results_path = out_dir / "results.jsonl"
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("残り"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(args.suite, total=len(plan))
        for group, spec, rep in plan:
            names = "+".join(t.name for t in group)
            run_id = f"{args.suite}__{names}__{spec.name}__r{rep + 1}__{datetime.now().strftime('%H%M%S')}"
            progress.update(task, description=f"{names} {spec.name} ({rep + 1}/{spec.repeats})")

            if spec.drop_caches:
                drop_caches()
            bw_prefix = None
            if spec.bw_log:
                (out_dir / "bwlog").mkdir(exist_ok=True)
                bw_prefix = out_dir / "bwlog" / run_id
            cmd = build_command(spec, [(t, target_size(t, default_size)) for t in group], bw_log_prefix=bw_prefix)

            thermal_before = smart_thermal_all(ctrls)
            with TempMonitor(float(defaults.get("temp_interval", 1.0))) as mon:
                stdout = run_cmd(cmd, sudo=need_sudo)
            thermal_after = smart_thermal_all(ctrls)

            raw = json.loads(stdout[stdout.index("{") :])  # fio は JSON の前に警告を出すことがある
            (out_dir / "fio" / f"{run_id}.json").write_text(json.dumps(raw, indent=1))
            (out_dir / "temps" / f"{run_id}.json").write_text(json.dumps(mon.samples))
            res: FioResult = parse_fio_json(raw)

            row = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "label": args.label,
                "suite": args.suite,
                "test": spec.name,
                "targets": [t.name for t in group],
                "repeat": rep + 1,
                "bw_bytes": res.bw_bytes,
                "iops": res.iops,
                "lat_mean_us": res.lat_mean_us,
                "lat_p99_us": res.lat_p99_us,
                "wall_s": res.wall_seconds,
                "jobs": [vars(j) for j in res.jobs],
                "temp_max": mon.max_temps,
                "thermal_before": thermal_before,
                "thermal_after": thermal_after,
                "fio_version": raw.get("fio version"),
                "cmd": shlex.join(cmd),
            }
            with results_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

            temps = " ".join(f"{k}={v:.0f}℃" for k, v in sorted(mon.max_temps.items()))
            log.info(
                "%s %s r%d: %s, %s IOPS, 平均 %.0f μs, p99 %.0f μs, %.1f 秒 (最高温度 %s)",
                names, spec.name, rep + 1, fmt_bw(res.bw_bytes), f"{res.iops:,.0f}",
                res.lat_mean_us, res.lat_p99_us, res.wall_seconds, temps,
            )
            # スロットリングの累計回数が増えていたら警告する
            for c in ctrls:
                for k in ("thm_temp1_trans_count", "thm_temp2_trans_count"):
                    b, a = thermal_before.get(c, {}).get(k), thermal_after.get(c, {}).get(k)
                    if b is not None and a is not None and a > b:
                        log.warning("%s で温度によるスロットリングが発生しました (%s: %s → %s)", c, k, b, a)
            progress.advance(task)
            time.sleep(float(defaults.get("cooldown", 0)))

    log.info("完了: %s", results_path)
    show_compare([out_dir], suite_filter=args.suite)


def load_rows(run_dir: Path) -> list[dict[str, Any]]:
    """runs/<label>/results.jsonl を読む。"""
    path = run_dir / "results.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def show_compare(run_dirs: list[Path], suite_filter: str | None = None) -> None:
    """ラベルごとの中央値を並べた表を出す。2つ目以降には1つ目に対する倍率を添える。"""
    # (suite, test, 対象) → ラベル → 繰り返しごとの行
    table_data: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = {}
    labels: list[str] = []
    for d in run_dirs:
        label = d.name
        labels.append(label)
        for row in load_rows(d):
            if suite_filter and row["suite"] != suite_filter:
                continue
            key = (row["suite"], row["test"], "+".join(row["targets"]))
            table_data.setdefault(key, {}).setdefault(label, []).append(row)

    table = Table(title="計測結果 (繰り返しの中央値)", show_lines=False)
    for col in ("suite", "test", "対象"):
        table.add_column(col, style="cyan" if col == "test" else None)
    for label in labels:
        table.add_column(label, justify="right")

    base_label = labels[0]
    for key in sorted(table_data, key=lambda k: (k[0], k[2], _test_order(k[1]))):
        by_label = table_data[key]
        cells: list[str] = []
        base_bw = None
        for label in labels:
            rows = by_label.get(label)
            if not rows:
                cells.append("-")
                continue
            bw = statistics.median(r["bw_bytes"] for r in rows)
            iops = statistics.median(r["iops"] for r in rows)
            wall = statistics.median(r["wall_s"] for r in rows)
            cell = fmt_bw(bw)
            if "RND" in key[1]:
                cell += f"\n{iops:,.0f} IOPS"
            if key[0] in ("coldread", "sustained"):
                cell += f"\n{wall:.1f} 秒"
            if label == base_label:
                base_bw = bw
            elif base_bw:
                ratio = bw / base_bw
                color = "green" if ratio >= 1.1 else "red" if ratio <= 0.9 else "white"
                cell += f"\n[{color}]×{ratio:.2f}[/{color}]"
            cells.append(cell)
        table.add_row(*key, *cells)
    console.print(table)


def _test_order(name: str) -> tuple[int, str]:
    """表の並び順: 読み込み → 書き込み、その中は名前順。"""
    return (1 if "write" in name else 0, name)


def build_parser() -> argparse.ArgumentParser:
    """引数の定義。"""
    p = argparse.ArgumentParser(prog="nvme-bench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="suite を実行して runs/<label>/ に保存する")
    r.add_argument("--config", default=str(REPO / "configs" / "default.yaml"), help="設定ファイル (既定: configs/default.yaml)")
    r.add_argument("--label", required=True, help="結果の保存先 runs/<label>/ の名前 (例: single, raid0)")
    r.add_argument("--suite", required=True, help="設定の suites のキー (cdm / concurrent / sustained / coldread)")
    r.add_argument("--target", action="append", required=True, help="設定の targets のキー。複数指定可")
    r.add_argument("--only", action="append", help="test 名に含まれる文字列で絞る (複数指定可)")
    r.add_argument("--allow-destroy", action="append", metavar="DEV", help="書き込みを許す生デバイス (例: /dev/nvme0n1)。中身は消える")
    r.add_argument("--no-precondition", action="store_true", help="計測範囲の書き埋め・計測用ファイルの作り直しを省く")
    r.add_argument("--no-env", action="store_true", help="env.md (計測環境) を記録しない")
    r.add_argument("--log", help="ログファイル (既定: runs/<label>/run.log)")
    r.add_argument("--runtime", type=int, help="1回の計測時間 (秒)。設定の defaults を上書き")
    r.add_argument("--ramp-time", type=int, help="助走時間 (秒)")
    r.add_argument("--repeats", type=int, help="繰り返し回数")
    r.add_argument("--size", help="計測範囲 (例: 64g)")
    r.add_argument("--cooldown", type=float, help="計測間の待ち時間 (秒)")
    r.set_defaults(func=run_suite)

    c = sub.add_parser("compare", help="複数の runs/<label>/ を並べて比較する")
    c.add_argument("runs", nargs="+", help="runs/<label> のディレクトリ (1つ目が倍率の基準)")
    c.add_argument("--suite", help="この suite だけを表示する")
    c.set_defaults(func=lambda a: show_compare([Path(x) for x in a.runs], a.suite))
    return p


def main() -> None:
    """エントリポイント。"""
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
