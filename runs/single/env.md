# 計測環境 (2026-10-19 12:21:56 JST)

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
Mem:              89          11          76           0           2          78
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
  path=pci0000:00/0000:00:03.1/0000:78:00.0
  link: 16.0 GT/s PCIe x2 (max 16.0 GT/s PCIe x4)
  upstream 0000:00:03.1: 16.0 GT/s PCIe x2 (max 32.0 GT/s PCIe x2)
```

## NVMe の詳細 (nvme id-ctrl / LBA フォーマット / SMART。要 sudo)

```
nvme0 sn        : (公開のため削除)
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
nvme1 sn        : (公開のため削除)
nvme1 mn        : CT2000T500SSD8                          
nvme1 fr        : P8CR002 
nvme1 mdts      : 7
nvme1 wctemp    : 359
nvme1 cctemp    : 361
nvme1 hmpre     : 0
nvme1 hmmin     : 0
nvme1n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme1 temperature				: 44 °C (317 K, 111 °F)
nvme1 percentage_used				: 3%
nvme2 sn        : (公開のため削除)
nvme2 mn        : CT2000T500SSD8                          
nvme2 fr        : P8CR002 
nvme2 mdts      : 7
nvme2 wctemp    : 359
nvme2 cctemp    : 361
nvme2 hmpre     : 0
nvme2 hmmin     : 0
nvme2n1 lbaf  0 : ms:0   lbads:9  rp:0x1 (in use)
nvme2 temperature				: 56 °C (329 K, 132 °F)
nvme2 percentage_used				: 3%
```

## ブロック層の設定

```
nvme0n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme1n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
nvme2n1: scheduler=[none] mq-deadline  nr_requests=1023 read_ahead_kb=128 max_sectors_kb=128
NAME        MODEL           SIZE FSTYPE MOUNTPOINTS
nvme1n1     CT2000T500SSD8  1.8T        
├─nvme1n1p1                 1.8T btrfs  /tmp
│                                       /var/log
│                                       /var/cache
│                                       /srv
│                                       /home
│                                       /root
│                                       /
└─nvme1n1p2                   1G vfat   /boot/efi
nvme2n1     CT2000T500SSD8  1.8T        
nvme0n1     CT2000T500SSD8  1.8T        
└─nvme0n1p1                 1.8T        
```

## btrfs (ルートのファイルシステム)

```
/dev/nvme1n1p1[/@] rw,relatime,ssd,discard=async,space_cache=v2,subvolid=256,subvol=/@
Label: none  uuid: acb63bf0-ab89-4069-bb64-d3352482c507
	Total devices 1 FS bytes used 606.85GiB
	devid    1 size 1.82TiB used 655.02GiB path /dev/nvme1n1p1
Overall:
    Device size:		   1.82TiB
    Device allocated:		 655.02GiB
    Device unallocated:		   1.18TiB
    Device missing:		     0.00B
    Device slack:		     0.00B
    Used:			 609.76GiB
    Free (estimated):		   1.22TiB	(min: 644.53GiB)
    Free (statfs, df):		   1.22TiB
    Data ratio:			      1.00
    Metadata ratio:		      2.00
    Global reserve:		 512.00MiB	(used: 0.00B)
    Multiple profiles:		        no

                  Data      Metadata System                            
Id Path           single    DUP      DUP      Unallocated Total   Slack
-- -------------- --------- -------- -------- ----------- ------- -----
 1 /dev/nvme1n1p1 645.01GiB 10.00GiB 16.00MiB     1.18TiB 1.82TiB     -
-- -------------- --------- -------- -------- ----------- ------- -----
   Total          645.01GiB  5.00GiB  8.00MiB     1.18TiB 1.82TiB 0.00B
   Used           603.95GiB  2.90GiB 96.00KiB                          
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
(未コミット)
?? .gitignore
?? LICENSE
?? README.ja.md
?? configs/
?? docs/
?? pyproject.toml
?? runs/
?? scripts/
?? src/
?? tests/
?? uv.lock
```
