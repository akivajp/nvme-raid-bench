# 計測環境 (2026-10-22 02:23:11 JST)

## マザーボード / BIOS

```
board_vendor: ASRock
board_name: X870 Taichi Creator
bios_version: 4.60
bios_date: 09/17/2026
```

## OS / カーネル / CPU / メモリ

```
PRETTY_NAME="Ubuntu 26.04.1 LTS"
7.0.0-38-generic
model name	: AMD Ryzen 9 9950X3D 16-Core Processor
32
               total        used        free      shared  buff/cache   available
Mem:              89          10          41           0          38          79
```

## NVMe (型番・ファームウェア・PCIe の接続経路とリンク)

```
nvme0: model=CT2000T500SSD8  fw=P8CR002  ns=nvme0n1 
  path=pci0000:00/0000:00:02.1/0000:04:00.0/0000:05:08.0/0000:11:00.0
  link: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:05:08.0: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:04:00.0: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:02.1: 16.0 GT/s PCIe x4 (max 32.0 GT/s PCIe x4)
nvme1: model=CT2000T500SSD8  fw=P8CR002  ns=nvme1n1 
  path=pci0000:00/0000:00:01.2/0000:02:00.0
  link: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:01.2: 16.0 GT/s PCIe x4 (max 32.0 GT/s PCIe x4)
nvme2: model=CT2000T500SSD8  fw=P8CR002  ns=nvme2n1 
  path=pci0000:00/0000:00:02.2/0000:14:00.0
  link: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:02.2: 16.0 GT/s PCIe x4 (max 32.0 GT/s PCIe x4)
```

## NVMe の詳細 (nvme id-ctrl / LBA フォーマット / SMART。要 sudo。シリアル番号は公開しないので記録しない)

```
```

## ブロック層の設定

```
nvme0n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme1n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme2n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
NAME        MODEL           SIZE FSTYPE MOUNTPOINTS
nvme1n1     CT2000T500SSD8  1.8T        
├─nvme1n1p1                 1.8T btrfs  /var/log
│                                       /var/cache
│                                       /tmp
│                                       /srv
│                                       /root
│                                       /home
│                                       /
└─nvme1n1p2                   1G vfat   /boot/efi
nvme0n1     CT2000T500SSD8  1.8T btrfs  
nvme2n1     CT2000T500SSD8  1.8T btrfs  
```

## btrfs (ルートのファイルシステム)

```
/dev/nvme1n1p1[/@] rw,relatime,ssd,discard=async,space_cache=v2,subvolid=256,subvol=/@
ERROR: cannot access '/root': Permission denied
Label: none  uuid: acb63bf0-ab89-4069-bb64-d3352482c507
	Total devices 3 FS bytes used 687.31GiB
	devid    1 size 0 used 0 path /dev/nvme1n1p1 MISSING
	devid    2 size 0 used 0 path /dev/nvme0n1 MISSING
	devid    3 size 0 used 0 path /dev/nvme2n1 MISSING
(btrfs filesystem usage は root 権限が必要なため未取得)
```

## ツール

```
fio-3.41
nvme version 2.16 (git 2.16)
btrfs-progs v6.17.1
-EXPERIMENTAL -INJECT -STATIC +LZO +ZSTD +UDEV +FSVERITY +ZONED CRYPTO=builtin
```

## 計測ツール

```
c25a15c0818cb611be86970038c3dcbaa3e073aa 2026-10-22 01:29:28 +0900
?? runs/meta-raid1/
?? runs/meta-raid1c3/
?? scripts/phase-metadata.sh
```
