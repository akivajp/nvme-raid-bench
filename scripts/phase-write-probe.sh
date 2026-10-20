#!/usr/bin/env bash
# btrfs の書き込みが遅い原因の切り分け。データのチェックサムあり (fs) となし (fs_nocow) で同じ計測を流す。
# 結果は runs/<label>/ (既定: write-probe)。終わったら計測用ファイルを消す。
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,3p' "$0"; echo "usage: $(basename "$0") [label]"; exit 0 ;; esac

LABEL="${1:-write-probe}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bench() { uv run nvme-bench run --label "$LABEL" "$@"; }

bench --suite write_probe --target fs
bench --suite write_probe --target fs_nocow
# 64GiB の計測用ファイルとジョブごとのファイルを残さない
rm -f ~/nvme-bench-scratch/fio-testfile* ~/nvme-bench-scratch/nocow/fio-testfile*
