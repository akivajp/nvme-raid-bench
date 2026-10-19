#!/usr/bin/env bash
# 計測の再現条件 (マザーボード・CPU・カーネル・NVMe の型番/ファームウェア/PCIe の接続経路・btrfs の構成・fio のバージョン) を
# Markdown で標準出力に書き出す。公開時の「検証環境」節の元データにする。
set -uo pipefail
case "${1:-}" in -h|--help) sed -n '2,3p' "$0"; echo "usage: $(basename "$0") > runs/<label>/env.md"; exit 0 ;; esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

section() { printf '\n## %s\n\n```\n' "$1"; }
endsec() { printf '```\n'; }

echo "# 計測環境 ($(date '+%F %T %Z'))"

section "マザーボード / BIOS"
for f in board_vendor board_name bios_version bios_date; do printf '%s: %s\n' "$f" "$(cat /sys/class/dmi/id/$f 2>/dev/null)"; done
endsec

section "OS / カーネル / CPU / メモリ"
grep PRETTY_NAME /etc/os-release; uname -r
grep -m1 'model name' /proc/cpuinfo; nproc
free -g | head -2
endsec

section "NVMe (型番・ファームウェア・PCIe の接続経路とリンク)"
for d in /sys/class/nvme/nvme*; do
  n=$(basename "$d"); dev=$(readlink -f "$d/device")
  printf '%s: model=%s fw=%s ns=%s\n' "$n" "$(tr -s ' ' < "$d/model")" "$(cat "$d/firmware_rev")" "$(ls -d "$d"/nvme*n* 2>/dev/null | xargs -n1 basename | tr '\n' ' ')"
  printf '  path=%s\n  link: %s x%s (max %s x%s)\n' "${dev#/sys/devices/}" \
    "$(cat "$dev/current_link_speed")" "$(cat "$dev/current_link_width")" "$(cat "$dev/max_link_speed")" "$(cat "$dev/max_link_width")"
  # 上流のブリッジ (ルートポート・チップセット) のリンクも記録する。ここが律速になりうるため
  p="$dev"
  while p=$(dirname "$p"); [[ -e "$p/current_link_width" ]]; do
    printf '  upstream %s: %s x%s (max %s x%s)\n' "$(basename "$p")" \
      "$(cat "$p/current_link_speed")" "$(cat "$p/current_link_width")" "$(cat "$p/max_link_speed")" "$(cat "$p/max_link_width")"
  done
done
endsec

section "NVMe の詳細 (nvme id-ctrl / LBA フォーマット / SMART。要 sudo。シリアル番号は公開しないので記録しない)"
for n in /dev/nvme[0-9]; do
  sudo -n nvme id-ctrl "$n" 2>/dev/null | grep -E '^(mn|fr|hmpre|hmmin|wctemp|cctemp|mdts) ' | sed "s|^|$(basename "$n") |"
  sudo -n nvme id-ns "${n}n1" 2>/dev/null | grep -E 'in use' | sed "s|^|$(basename "$n")n1 |"
  sudo -n nvme smart-log "$n" 2>/dev/null | grep -E 'temperature|percentage_used|data_units_written|thm_temp|warning_temp' | sed "s|^|$(basename "$n") |"
done
endsec

section "ブロック層の設定"
for b in /sys/block/nvme*n1; do
  printf '%s: scheduler=%s nr_requests=%s read_ahead_kb=%s max_sectors_kb=%s\n' "$(basename "$b")" \
    "$(cat "$b/queue/scheduler")" "$(cat "$b/queue/nr_requests")" "$(cat "$b/queue/read_ahead_kb")" "$(cat "$b/queue/max_sectors_kb")"
done
lsblk -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINTS -e 7
endsec

section "btrfs (ルートのファイルシステム)"
findmnt -no SOURCE,OPTIONS /
sudo -n btrfs filesystem show 2>/dev/null || btrfs filesystem show / 2>&1
sudo -n btrfs filesystem usage -T / 2>/dev/null || echo "(btrfs filesystem usage は root 権限が必要なため未取得)"
endsec

section "ツール"
fio --version; nvme version 2>/dev/null | head -1; btrfs --version
endsec

section "計測ツール"
git -C "$REPO" log -1 --format='%H %cd' --date=iso 2>/dev/null || echo "(未コミット)"
git -C "$REPO" status --short 2>/dev/null | head -20
endsec
