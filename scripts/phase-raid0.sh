#!/usr/bin/env bash
# RAID0 化した後の計測を流す。結果は runs/<label>/ (既定: raid0)。単体構成 (runs/single) と同じ条件で比べる。
# 生デバイスはファイルシステムに組み込まれているため測らない (btrfs 上のファイルとモデルファイルのみ)。
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,3p' "$0"; echo "usage: $(basename "$0") [label]"; exit 0 ;; esac

LABEL="${1:-raid0}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bench() { uv run nvme-bench run --label "$LABEL" "$@"; }

# Data が RAID0 になっていなければ止める (balance の途中や変換し忘れで測らないように)
if ! sudo -n btrfs filesystem df / | grep -q '^Data, RAID0'; then
  echo "Data が RAID0 ではありません。balance の完了を確認してください:" >&2
  sudo -n btrfs filesystem df / >&2
  exit 1
fi

# 計測用ファイルは作り直すので、新しい構成 (3台に分散) で配置される
bench --suite cdm --target fs
# GGUF は balance で再配置されたものを読む
bench --suite coldread --target gguf
bench --suite coldread_parallel --target gguf
uv run nvme-bench compare runs/single "runs/${LABEL}"
