#!/usr/bin/env bash
# btrfs で O_DIRECT の書き込みが本当にページキャッシュを迂回しているかを確かめる。
# O_DIRECT で 8GiB 書く間に、ページが Dirty にされた数 (/proc/vmstat の nr_dirtied の差) を、
# データのチェックサムあり (通常) となし (chattr +C のディレクトリ) のファイルで比べる。
# 本当の O_DIRECT ならページキャッシュを通らないので、ほぼ 0 になる。
# (Cached の増減では判別できない。フォールバック時もカーネルが書き出し後にページを破棄するため)
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,6p' "$0"; echo "usage: $(basename "$0") [btrfs 上の作業ディレクトリ (既定: ~/nvme-bench-scratch)]"; exit 0 ;; esac

DIR="${1:-$HOME/nvme-bench-scratch}"
mkdir -p "$DIR/nocow"
chattr +C "$DIR/nocow"   # 空のディレクトリに付けると、中に作るファイルが NOCOW (= NODATASUM) になる
dirtied() { awk '$1=="nr_dirtied" {print $2}' /proc/vmstat; }
for f in "$DIR/dio-check" "$DIR/nocow/dio-check"; do
  rm -f "$f"; sync
  a=$(dirtied)
  fio --name=c --filename="$f" --rw=write --bs=1m --iodepth=8 --ioengine=io_uring --direct=1 --size=8g --output-format=terse >/dev/null
  b=$(dirtied)
  echo "$(lsattr "$f" | cut -c1-22) $f: O_DIRECT で 8192 MiB 書き込み → Dirty にされたページ $(( (b-a)*4/1024 )) MiB 分"
  rm -f "$f"
done
