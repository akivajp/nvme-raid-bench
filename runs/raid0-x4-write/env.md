# 計測環境 (2026-10-20 09:10:00 JST)

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
Mem:              89           9          27           0          53          80
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
  path=pci0000:00/0000:00:02.2/0000:14:00.0
  link: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:02.2: 16.0 GT/s PCIe x4 (max 32.0 GT/s PCIe x4)
nvme2: model=CT2000T500SSD8  fw=P8CR002  ns=nvme2n1 
  path=pci0000:00/0000:00:01.2/0000:02:00.0
  link: 16.0 GT/s PCIe x4 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:01.2: 16.0 GT/s PCIe x4 (max 32.0 GT/s PCIe x4)
```

## NVMe の詳細 (nvme id-ctrl / LBA フォーマット / SMART。要 sudo。シリアル番号は公開しないので記録しない)

```
nvme0 mn        : CT2000T500SSD8                          
nvme0 fr        : P8CR002 
nvme0 mdts      : 7
nvme0 wctemp    : 359
nvme0 cctemp    : 361
nvme0 hmpre     : 0
nvme0 hmmin     : 0
nvme0n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme0 temperature				: 62 °C (335 K, 143 °F)
nvme0 percentage_used				: 3%
nvme1 mn        : CT2000T500SSD8                          
nvme1 fr        : P8CR002 
nvme1 mdts      : 7
nvme1 wctemp    : 359
nvme1 cctemp    : 361
nvme1 hmpre     : 0
nvme1 hmmin     : 0
nvme1n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme1 temperature				: 64 °C (337 K, 147 °F)
nvme1 percentage_used				: 3%
nvme2 mn        : CT2000T500SSD8                          
nvme2 fr        : P8CR002 
nvme2 mdts      : 7
nvme2 wctemp    : 359
nvme2 cctemp    : 361
nvme2 hmpre     : 0
nvme2 hmmin     : 0
nvme2n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme2 temperature				: 49 °C (322 K, 120 °F)
nvme2 percentage_used				: 3%
```

## ブロック層の設定

```
nvme0n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme1n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme2n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
NAME        MODEL           SIZE FSTYPE MOUNTPOINTS
nvme2n1     CT2000T500SSD8  1.8T        
├─nvme2n1p1                 1.8T btrfs  /var/log
│                                       /var/cache
│                                       /tmp
│                                       /srv
│                                       /root
│                                       /home
│                                       /
└─nvme2n1p2                   1G vfat   /boot/efi
nvme1n1     CT2000T500SSD8  1.8T btrfs  
nvme0n1     CT2000T500SSD8  1.8T btrfs  
```

## btrfs (ルートのファイルシステム)

```
/dev/nvme2n1p1[/@] rw,relatime,ssd,discard=async,space_cache=v2,subvolid=256,subvol=/@
Label: none  uuid: acb63bf0-ab89-4069-bb64-d3352482c507
	Total devices 3 FS bytes used 687.02GiB
	devid    1 size 1.82TiB used 241.00GiB path /dev/nvme2n1p1
	devid    2 size 1.82TiB used 247.03GiB path /dev/nvme0n1
	devid    3 size 1.82TiB used 246.03GiB path /dev/nvme1n1
Overall:
    Device size:		   5.46TiB
    Device allocated:		 734.06GiB
    Device unallocated:		   4.74TiB
    Device missing:		     0.00B
    Device slack:		     0.00B
    Used:			 691.39GiB
    Free (estimated):		   4.78TiB	(min: 2.41TiB)
    Free (statfs, df):		   4.78TiB
    Data ratio:			      1.00
    Metadata ratio:		      2.00
    Global reserve:		 512.00MiB	(used: 0.00B)
    Multiple profiles:		        no

                  Data      Metadata System                            
Id Path           RAID0     RAID1    RAID1    Unallocated Total   Slack
-- -------------- --------- -------- -------- ----------- ------- -----
 1 /dev/nvme2n1p1 240.00GiB  1.00GiB        -     1.58TiB 1.82TiB     -
 2 /dev/nvme0n1   240.00GiB  7.00GiB 32.00MiB     1.58TiB 1.82TiB     -
 3 /dev/nvme1n1   240.00GiB  6.00GiB 32.00MiB     1.58TiB 1.82TiB     -
-- -------------- --------- -------- -------- ----------- ------- -----
   Total          720.00GiB  7.00GiB 32.00MiB     4.74TiB 5.46TiB 0.00B
   Used           682.66GiB  4.36GiB 80.00KiB                          
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
1b6f32cbb56f9d80bfb724fdca942f409450d8ed 2026-10-19 21:58:10 +0900
 M configs/default.yaml
 M scripts/phase-raid0.sh
 M src/nvme_raid_bench/cli.py
 M src/nvme_raid_bench/fio.py
 M src/nvme_raid_bench/monitor.py
 M tests/test_fio.py
?? runs/raid0-x4-write/
?? runs/raid0-x4/
?? scripts/phase-write-probe.sh
```
