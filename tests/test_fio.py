"""fio.py (コマンド組み立て・結果の集計・生デバイスの安全確認) のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from nvme_raid_bench.fio import (
    Target,
    TestSpec,
    build_command,
    device_busy_reasons,
    job_size,
    parse_fio_json,
    parse_size,
)

DEFAULTS = {"ioengine": "io_uring", "direct": 1, "runtime": 20, "ramp_time": 3, "repeats": 3, "size": "64g"}


def spec(**kw: object) -> TestSpec:
    base = {"name": "t", "rw": "read", "bs": "1m", "iodepth": 8, "numjobs": 1}
    return TestSpec.from_dict({**base, **kw}, DEFAULTS)


def test_parse_size() -> None:
    assert parse_size("64g") == 64 * 1024**3
    assert parse_size("1M") == 1024**2
    assert parse_size("4k") == 4096
    assert parse_size("300GiB") == 300 * 1024**3
    assert parse_size(512) == 512
    with pytest.raises(ValueError):
        parse_size("abc")


def test_test_spec_overrides_defaults() -> None:
    s = spec(runtime=10, repeats=1)
    assert s.runtime == 10 and s.repeats == 1
    assert s.ramp_time == 3  # 指定しなければ defaults が入る
    assert spec(rw="randwrite").is_write and not spec(rw="randread").is_write


def test_job_size_splits_range_for_multiple_jobs() -> None:
    # 4ジョブなら範囲を4等分し、各ジョブはブロックサイズの倍数になる
    assert job_size(spec(numjobs=4), 0) == 16 * 1024**3
    # size: full はファイル全体。端数はブロックサイズに切り下げる
    assert job_size(spec(size="full", numjobs=4), 10 * 1024**2 + 123) == 2 * 1024**2


def test_build_command_offsets_and_readonly() -> None:
    t = Target("gguf", "file", Path("/x/model.gguf"), readonly=True)
    cmd = build_command(spec(numjobs=4, size="full", time_based=False), [(t, 8 * 1024**2)])
    assert "--readonly" in cmd
    assert "--offset_increment=2097152" in cmd and "--size=2097152" in cmd
    assert not any(a.startswith("--runtime") for a in cmd)  # 全体を1回読む計測は時間で区切らない


def test_build_command_concurrent_jobs() -> None:
    a = Target("nvme0", "device", Path("/dev/nvme0n1"))
    b = Target("nvme2", "device", Path("/dev/nvme2n1"))
    cmd = build_command(spec(), [(a, 2 * 1024**4), (b, 2 * 1024**4)])
    assert cmd.count("--name=nvme0") == 1 and cmd.count("--name=nvme2") == 1
    assert "--runtime=20" in cmd and "--ramp_time=3" in cmd


def _job(name: str, *, read_bw: float = 0, write_bw: float = 0, iops: float = 100, mean_ns: float = 1000) -> dict:
    def side(bw: float) -> dict:
        return {
            "bw_bytes": bw,
            "iops": iops if bw else 0,
            "io_bytes": int(bw * 10),
            "runtime": 10000 if bw else 0,
            "clat_ns": {"mean": mean_ns, "percentile": {"99.000000": 5000, "99.900000": 9000}},
        }

    return {"jobname": name, "read": side(read_bw), "write": side(write_bw), "usr_cpu": 1.0, "sys_cpu": 2.0}


def test_parse_fio_json_merges_numjobs_and_sums_targets() -> None:
    data = {
        "jobs": [
            # 同じ対象の numjobs=2 は1つにまとめる
            _job("nvme0", read_bw=1e9, iops=100, mean_ns=1000),
            _job("nvme0", read_bw=1e9, iops=300, mean_ns=3000),
            # 別の対象は別のジョブとして持ち、合計は全体の値になる
            _job("nvme2", read_bw=5e8, iops=100, mean_ns=2000),
        ]
    }
    res = parse_fio_json(data)
    assert [j.name for j in res.jobs] == ["nvme0", "nvme2"]
    nvme0 = res.jobs[0]
    assert nvme0.bw_bytes == 2e9 and nvme0.iops == 400
    assert nvme0.lat_mean_us == pytest.approx((1 * 100 + 3 * 300) / 400)  # IOPS で重み付けした平均
    assert nvme0.sys_cpu == 4.0
    assert res.bw_bytes == 2.5e9 and res.iops == 500
    assert res.lat_p99_us == 5.0
    assert res.wall_seconds == 10.0


def test_parse_fio_json_uses_write_side_for_writes() -> None:
    res = parse_fio_json({"jobs": [_job("fs", write_bw=3e9)]})
    assert res.bw_bytes == 3e9


def _fake_sysblock(tmp_path: Path, holders: list[str] | None = None) -> Path:
    base = tmp_path / "nvme0n1"
    (base / "holders").mkdir(parents=True)
    part = base / "nvme0n1p1"
    (part / "holders").mkdir(parents=True)
    (part / "partition").write_text("1\n")
    for h in holders or []:
        (part / "holders" / h).mkdir()
    return tmp_path


def test_device_busy_reasons_free_device(tmp_path: Path) -> None:
    sysblock = _fake_sysblock(tmp_path)
    mounts = "/dev/nvme1n1p1 / btrfs rw 0 0\n"
    assert device_busy_reasons(Path("/dev/nvme0n1"), sysblock, mounts) == []


def test_device_busy_reasons_detects_mounted_partition(tmp_path: Path) -> None:
    sysblock = _fake_sysblock(tmp_path)
    mounts = "/dev/nvme0n1p1 /mnt btrfs rw 0 0\n"
    reasons = device_busy_reasons(Path("/dev/nvme0n1"), sysblock, mounts)
    assert reasons and "nvme0n1p1" in reasons[0]


def test_device_busy_reasons_detects_holders(tmp_path: Path) -> None:
    sysblock = _fake_sysblock(tmp_path, holders=["dm-0"])
    reasons = device_busy_reasons(Path("/dev/nvme0n1"), sysblock, "")
    assert reasons and "dm-0" in reasons[0]


def test_device_busy_reasons_missing_device(tmp_path: Path) -> None:
    assert device_busy_reasons(Path("/dev/nvme9n1"), tmp_path, "")


def test_build_command_separate_files_and_end_fsync() -> None:
    t = Target("fs", "file", Path("/scratch/fio-testfile"))
    cmd = build_command(spec(rw="write", numjobs=4, separate_files=True, end_fsync=True), [(t, 0)])
    # ジョブごとの別ファイル: --filename ではなく --directory と --filename_format を使い、範囲はずらさない
    assert "--directory=/scratch" in cmd and "--filename_format=fio-testfile.$jobnum" in cmd
    assert not any(a.startswith("--filename=") or a.startswith("--offset_increment") for a in cmd)
    assert "--end_fsync=1" in cmd
