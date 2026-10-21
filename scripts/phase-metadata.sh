#!/usr/bin/env bash
# メタデータのプロファイル (RAID1 / RAID1C3) による書き込みへの影響を測る。結果は runs/<label>/。
#   1. CrystalDiskMark 相当の書き込み 6種 (nvme-bench の cdm suite の *_write)
#   2. 空ファイルの大量作成 (fio の filecreate。4 ジョブ × 50,000 個、最後の sync まで含めた実時間)
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,4p' "$0"; echo "usage: $(basename "$0") <label>"; exit 0 ;; esac
LABEL="${1:?label を指定してください (例: meta-raid1)}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="runs/${LABEL}"; mkdir -p "$OUT"
sudo_df() { btrfs filesystem df / 2>/dev/null || true; }
sudo_df > "$OUT/btrfs-df.txt"

uv run nvme-bench run --label "$LABEL" --suite cdm --target fs --only _write

DIR="${HOME}/nvme-bench-scratch/filecreate"
for r in 1 2 3; do
  rm -rf "$DIR"; mkdir -p "$DIR"; sync
  t0=$(date +%s.%N)
  fio --name=fc --ioengine=filecreate --directory="$DIR" --filename_format='f.$jobnum.$filenum' \
      --nrfiles=50000 --filesize=4k --openfiles=1 --numjobs=4 --create_on_open=1 --output-format=json > "$OUT/filecreate-r$r.json"
  sync
  t1=$(date +%s.%N)
  printf 'filecreate r%d: 200000 files, %.2f s (sync included)\n' "$r" "$(echo "$t1-$t0" | bc)" | tee -a "$OUT/filecreate.txt"
done
rm -rf "$DIR" "${HOME}/nvme-bench-scratch/fio-testfile"
