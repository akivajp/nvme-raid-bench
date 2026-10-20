# 計測環境 (2026-10-20 08:49:50 JST)

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
Mem:              89           9          70           0          10          80
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
nvme0 temperature				: 56 °C (329 K, 132 °F)
nvme0 percentage_used				: 3%
nvme1 mn        : CT2000T500SSD8                          
nvme1 fr        : P8CR002 
nvme1 mdts      : 7
nvme1 wctemp    : 359
nvme1 cctemp    : 361
nvme1 hmpre     : 0
nvme1 hmmin     : 0
nvme1n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme1 temperature				: 58 °C (331 K, 136 °F)
nvme1 percentage_used				: 3%
nvme2 mn        : CT2000T500SSD8                          
nvme2 fr        : P8CR002 
nvme2 mdts      : 7
nvme2 wctemp    : 359
nvme2 cctemp    : 361
nvme2 hmpre     : 0
nvme2 hmmin     : 0
nvme2n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme2 temperature				: 45 °C (318 K, 113 °F)
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
	Total devices 3 FS bytes used 617.17GiB
	devid    1 size 1.82TiB used 216.00GiB path /dev/nvme2n1p1
	devid    2 size 1.82TiB used 222.03GiB path /dev/nvme0n1
	devid    3 size 1.82TiB used 221.03GiB path /dev/nvme1n1
Overall:
    Device size:		   5.46TiB
    Device allocated:		 659.06GiB
    Device unallocated:		   4.81TiB
    Device missing:		     0.00B
    Device slack:		     0.00B
    Used:			 621.20GiB
    Free (estimated):		   4.84TiB	(min: 2.44TiB)
    Free (statfs, df):		   4.84TiB
    Data ratio:			      1.00
    Metadata ratio:		      2.00
    Global reserve:		 512.00MiB	(used: 0.00B)
    Multiple profiles:		        no

                  Data      Metadata System                            
Id Path           RAID0     RAID1    RAID1    Unallocated Total   Slack
-- -------------- --------- -------- -------- ----------- ------- -----
 1 /dev/nvme2n1p1 215.00GiB  1.00GiB        -     1.61TiB 1.82TiB     -
 2 /dev/nvme0n1   215.00GiB  7.00GiB 32.00MiB     1.60TiB 1.82TiB     -
 3 /dev/nvme1n1   215.00GiB  6.00GiB 32.00MiB     1.60TiB 1.82TiB     -
-- -------------- --------- -------- -------- ----------- ------- -----
   Total          645.00GiB  7.00GiB 32.00MiB     4.81TiB 5.46TiB 0.00B
   Used           613.15GiB  4.03GiB 80.00KiB                          
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
 M scripts/phase-raid0.sh
?? runs/raid0-x4/
```
