"""fio の並列読み込みで、fio が報告する量と実際にディスクから読んだ量を比べる。

fio の mmap エンジンは numjobs > 1 だと offset_increment が効かず、全ジョブが同じ範囲を読む。
そのため fio の報告 (io_bytes・帯域) は正しく見えても、ディスクからは 1/numjobs しか読んでいない。
/proc/diskstats の読み出しセクタ数の差分で確かめる (要: sudo -n sysctl -w vm.drop_caches=3)。

usage: uv run python scripts/verify_mmap.py FILE [--dev nvme1n1p1 --dev nvme0n1 ...]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time


def disk_read_bytes(devs: set[str]) -> int:
    """指定デバイスから読み出したバイト数の累計 (/proc/diskstats の6列目は 512 バイト単位のセクタ数)。"""
    total = 0
    with open("/proc/diskstats") as f:
        for line in f:
            cols = line.split()
            if cols[2] in devs:
                total += int(cols[5]) * 512
    return total


def main() -> None:
    """エンジンと並列数の組み合わせごとに、キャッシュを捨ててからファイル全体を読む。"""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="読むファイル (例: GGUF)")
    p.add_argument("--dev", action="append", help="読み出し量を数えるデバイス名 (既定: RAID0 の3台)")
    args = p.parse_args()
    devs = set(args.dev or ["nvme1n1p1", "nvme0n1", "nvme2n1"])

    size = os.path.getsize(args.file)
    for eng, nj in [("mmap", 8), ("mmap", 4), ("mmap", 1), ("psync", 8)]:
        per = size // nj // 2**20 * 2**20  # 1ジョブの範囲 (1MiB の倍数)
        os.sync()
        subprocess.run(["sudo", "-n", "sysctl", "-w", "vm.drop_caches=3"], check=True, capture_output=True)
        a, t0 = disk_read_bytes(devs), time.monotonic()
        out = subprocess.run(
            ["fio", "--name=g", f"--filename={args.file}", "--readonly", "--rw=read", "--bs=1m",
             f"--ioengine={eng}", "--direct=0", f"--numjobs={nj}", f"--size={per}",
             f"--offset_increment={per}", "--group_reporting", "--output-format=json"],
            check=True, capture_output=True, text=True,
        ).stdout
        t1, b = time.monotonic(), disk_read_bytes(devs)
        io = json.loads(out[out.index("{"):])["jobs"][0]["read"]["io_bytes"]
        print(f"{eng:6s} x{nj}: fio io={io / 1e9:5.1f} GB  disk={(b - a) / 1e9:5.1f} GB  "
              f"wall={t1 - t0:5.1f} s  disk_rate={(b - a) / 1e9 / (t1 - t0):5.1f} GB/s", flush=True)


if __name__ == "__main__":
    main()
