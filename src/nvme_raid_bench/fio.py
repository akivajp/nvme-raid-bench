"""fio のコマンド組み立て・結果 (JSON) の集計・生デバイスの安全確認。

副作用を持たない関数だけを置き、単体テストの対象にする。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# fio のサイズ表記 (1024 単位。fio の既定の kb_base=1024 と合わせる)
_SIZE_UNITS = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}


def parse_size(text: str | int) -> int:
    """'64g' / '1m' / 4096 のようなサイズ表記をバイト数に変換する。"""
    if isinstance(text, int):
        return text
    m = re.fullmatch(r"\s*(\d+)\s*([kmgt]?)i?b?\s*", text.lower())
    if not m:
        raise ValueError(f"サイズ表記を解釈できません: {text!r}")
    return int(m.group(1)) * _SIZE_UNITS[m.group(2)]


@dataclass
class Target:
    """計測対象 (btrfs 上のファイル、または生デバイス)。"""

    name: str
    kind: str  # "file" | "device"
    path: Path
    readonly: bool = False
    nocow: bool = False  # 置き場所のディレクトリに chattr +C を付ける (btrfs の CoW とデータのチェックサムを無効にする)

    @property
    def is_device(self) -> bool:
        """生デバイスかどうか。"""
        return self.kind == "device"


@dataclass
class TestSpec:
    """1つの計測条件。辞書 (YAML) から作り、既定値を補完した状態で持つ。"""

    __test__ = False  # 名前が Test で始まるため、pytest がテストクラスとして集めないようにする

    name: str
    rw: str
    bs: str
    iodepth: int
    numjobs: int
    ioengine: str
    direct: int
    size: str  # "64g" のような表記、または "full" (ファイル全体)
    runtime: int
    ramp_time: int
    time_based: bool = True
    repeats: int = 3
    drop_caches: bool = False
    bw_log: bool = False
    separate_files: bool = False  # numjobs > 1 のとき、1つのファイルを分け合わずジョブごとに別ファイルへ読み書きする
    end_fsync: bool = False  # 終了時に fsync する (バッファ書き込みをディスクに届くまで測る)

    @property
    def is_write(self) -> bool:
        """書き込みを含む計測かどうか。"""
        return "write" in self.rw or self.rw in ("rw", "randrw", "trim", "randtrim")

    @classmethod
    def from_dict(cls, d: dict[str, Any], defaults: dict[str, Any]) -> TestSpec:
        """YAML の test 定義に defaults を補完して作る。"""
        merged = {**defaults, **d}
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: merged[k] for k in keys if k in merged})


def job_size(spec: TestSpec, target_bytes: int) -> int:
    """1ジョブあたりの計測範囲 (バイト)。

    numjobs > 1 のときは範囲を等分し、各ジョブが重ならない領域を担当する
    (同じ先頭から読むと、シーケンシャルの計測が実質的に同じ箇所の読み直しになるため)。
    範囲はブロックサイズの倍数に切り下げる。
    """
    total = target_bytes if spec.size == "full" else parse_size(spec.size)
    per_job = total // spec.numjobs
    bs = parse_size(spec.bs)
    return per_job - per_job % bs


def build_job_args(spec: TestSpec, target: Target, target_bytes: int) -> list[str]:
    """1つの対象に対する fio のジョブ引数 (--name 以降) を作る。"""
    per_job = job_size(spec, target_bytes)
    if spec.separate_files and target.kind == "file":
        # ジョブごとに <ファイル名>.<ジョブ番号> という別ファイルを使う (btrfs はファイル単位でロックや書き出しが直列になるため、その影響を見る)
        where = [f"--directory={target.path.parent}", f"--filename_format={target.path.name}.$jobnum"]
    else:
        where = [f"--filename={target.path}"]
    args = [
        f"--name={target.name}",
        *where,
        f"--rw={spec.rw}",
        f"--bs={spec.bs}",
        f"--iodepth={spec.iodepth}",
        f"--numjobs={spec.numjobs}",
        f"--ioengine={spec.ioengine}",
        f"--direct={spec.direct}",
        f"--size={per_job}",
    ]
    if spec.numjobs > 1 and not spec.separate_files:
        # ジョブごとに先頭をずらし、互いに重ならない範囲を読み書きさせる
        args.append(f"--offset_increment={per_job}")
    if spec.end_fsync:
        args.append("--end_fsync=1")
    if target.readonly:
        args.append("--readonly")
    return args


def build_command(
    spec: TestSpec,
    targets: list[tuple[Target, int]],
    *,
    bw_log_prefix: Path | None = None,
) -> list[str]:
    """fio の完全なコマンド (sudo は含まない) を作る。

    targets は (対象, 対象のサイズ) の組。複数を渡すと1回の fio で同時に動かす。
    """
    cmd = ["fio", "--output-format=json", "--group_reporting=0"]
    if spec.time_based:
        cmd += ["--time_based=1", f"--runtime={spec.runtime}", f"--ramp_time={spec.ramp_time}"]
    # ランダムの位置を毎回同じにして再現性を持たせる (fio の既定でも固定だが明示する)
    cmd += ["--randrepeat=1", "--norandommap=1", "--random_generator=tausworthe64"]
    # 書き込むデータは fio の既定 (起動時に1回だけ作るランダムなバッファ) のまま。
    # --refill_buffers で毎回作り直すと、10GB/s 級では CPU が律速になりうる。
    # btrfs の圧縮は無効で、T500 (Phison E25) にも圧縮・重複排除は無いため、既定で問題ない
    if bw_log_prefix is not None:
        cmd += [f"--write_bw_log={bw_log_prefix}", "--log_avg_msec=1000"]
    for target, size in targets:
        cmd += build_job_args(spec, target, size)
    return cmd


def build_precondition_command(target: Target, size_bytes: int) -> list[str]:
    """生デバイスの計測範囲を一度シーケンシャルに書き埋める fio コマンド。"""
    return [
        "fio",
        "--output-format=json",
        f"--name=precondition-{target.name}",
        f"--filename={target.path}",
        "--rw=write",
        "--bs=1m",
        "--iodepth=32",
        "--ioengine=io_uring",
        "--direct=1",
        f"--size={size_bytes}",
    ]


@dataclass
class JobResult:
    """fio の1ジョブ (= 1対象) の結果。"""

    name: str
    bw_bytes: float  # 1秒あたりのバイト数
    iops: float
    lat_mean_us: float
    lat_p99_us: float
    lat_p999_us: float
    io_bytes: int
    runtime_ms: int
    usr_cpu: float
    sys_cpu: float


@dataclass
class FioResult:
    """1回の fio 実行の結果。複数ジョブ (同時計測) の場合は合計を持つ。"""

    jobs: list[JobResult] = field(default_factory=list)

    @property
    def bw_bytes(self) -> float:
        """全ジョブの合計帯域 (B/s)。"""
        return sum(j.bw_bytes for j in self.jobs)

    @property
    def iops(self) -> float:
        """全ジョブの合計 IOPS。"""
        return sum(j.iops for j in self.jobs)

    @property
    def lat_mean_us(self) -> float:
        """完了レイテンシの平均 (IOPS で重み付け)。"""
        total = self.iops
        if total == 0:
            return 0.0
        return sum(j.lat_mean_us * j.iops for j in self.jobs) / total

    @property
    def lat_p99_us(self) -> float:
        """99 パーセンタイルのレイテンシ (ジョブ間の最大。合算はできないので最悪値で代表させる)。"""
        return max((j.lat_p99_us for j in self.jobs), default=0.0)

    @property
    def wall_seconds(self) -> float:
        """最も長く掛かったジョブの実行時間 (秒)。ファイル全体を読む計測の所要時間になる。"""
        return max((j.runtime_ms for j in self.jobs), default=0) / 1000


def _pct(clat: dict[str, Any], key: str) -> float:
    """clat_ns のパーセンタイルを μs で取り出す (無ければ 0)。"""
    return float(clat.get("percentile", {}).get(key, 0)) / 1000


def parse_fio_json(data: dict[str, Any]) -> FioResult:
    """fio の JSON 出力を集計する。

    group_reporting=0 のため、numjobs > 1 だとジョブ名ごとに複数の要素が並ぶ。
    同じ名前 (= 同じ対象) の要素を合算して1つの JobResult にする。
    """
    by_name: dict[str, list[dict[str, Any]]] = {}
    for job in data.get("jobs", []):
        by_name.setdefault(job["jobname"], []).append(job)

    result = FioResult()
    for name, jobs in by_name.items():
        bw = iops = lat_weighted = 0.0
        io_bytes = 0
        runtime_ms = 0
        p99 = p999 = 0.0
        usr = sys_ = 0.0
        for job in jobs:
            # 読み込みと書き込みのうち、実際に I/O があった方を使う (混在の計測はしない前提)
            side = job["write"] if job["write"]["io_bytes"] > 0 else job["read"]
            clat = side.get("clat_ns", {})
            bw += side["bw_bytes"]
            iops += side["iops"]
            lat_weighted += clat.get("mean", 0) / 1000 * side["iops"]
            io_bytes += side["io_bytes"]
            runtime_ms = max(runtime_ms, side["runtime"])
            p99 = max(p99, _pct(clat, "99.000000"))
            p999 = max(p999, _pct(clat, "99.900000"))
            usr += job.get("usr_cpu", 0.0)
            sys_ += job.get("sys_cpu", 0.0)
        result.jobs.append(
            JobResult(
                name=name,
                bw_bytes=bw,
                iops=iops,
                lat_mean_us=lat_weighted / iops if iops else 0.0,
                lat_p99_us=p99,
                lat_p999_us=p999,
                io_bytes=io_bytes,
                runtime_ms=runtime_ms,
                usr_cpu=usr,
                sys_cpu=sys_,
            )
        )
    return result


def device_busy_reasons(dev: Path, sys_block: Path = Path("/sys/block"), mounts_text: str | None = None) -> list[str]:
    """生デバイスに書き込んではいけない理由を列挙する (空なら書き込んでよい)。

    - デバイス自身やそのパーティションがマウントされている
    - デバイス自身やそのパーティションを、他のブロックデバイス (dm/md 等) が使っている
    btrfs のマルチデバイス構成に加えた後は、マウントの一覧に現れない (代表の1台しか載らない) ことがあるため、
    btrfs のシグネチャも呼び出し側で確認すること。
    """
    name = dev.name
    reasons: list[str] = []
    base = sys_block / name
    if not base.exists():
        return [f"{dev} はブロックデバイスとして見つかりません"]

    # デバイス自身とパーティションの名前を集める
    names = [name] + sorted(p.name for p in base.iterdir() if p.name.startswith(name) and (p / "partition").exists())
    if mounts_text is None:
        mounts_text = Path("/proc/mounts").read_text()
    mounted = {line.split()[0] for line in mounts_text.splitlines() if line.strip()}
    for n in names:
        if f"/dev/{n}" in mounted:
            reasons.append(f"/dev/{n} がマウントされています")
        holders = base / "holders" if n == name else base / n / "holders"
        if holders.exists() and any(holders.iterdir()):
            reasons.append(f"/dev/{n} を他のデバイスが使っています ({', '.join(h.name for h in holders.iterdir())})")
    return reasons
