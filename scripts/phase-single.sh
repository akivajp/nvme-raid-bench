#!/usr/bin/env bash
# 単体構成 (RAID0 化の前) の計測を一通り流す。結果は runs/<label>/ (既定: single)。
# 未使用の nvme0n1 / nvme2n1 の中身は消える。
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,3p' "$0"; echo "usage: $(basename "$0") [label]"; exit 0 ;; esac

LABEL="${1:-single}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
DESTROY=(--allow-destroy /dev/nvme0n1 --allow-destroy /dev/nvme2n1)
bench() { uv run nvme-bench run --label "$LABEL" "$@"; }

# 1. 対象ごとの CrystalDiskMark 相当 (btrfs 上のファイル = システムディスク nvme1、生デバイス2台)
bench --suite cdm --target fs
bench --suite cdm --target nvme0 "${DESTROY[@]}"
bench --suite cdm --target nvme2 "${DESTROY[@]}"
# 2. 3台同時 (RAID0 で出せる上限の見積もり)
bench --suite concurrent --target fs --target nvme0 --target nvme2 "${DESTROY[@]}"
# 3. モデルファイルをキャッシュの無い状態から読む
bench --suite coldread --target gguf
# 4. SLC キャッシュを使い切るまでの書き込み (TRIM してから。最後に流す)
bench --suite sustained --target nvme0 "${DESTROY[@]}"
bench --suite sustained --target nvme2 "${DESTROY[@]}"
