# nvme-raid-bench

NVMe SSD 単体と btrfs RAID0 の I/O 性能を `fio` で計測・比較するツール。

PCIe の接続経路 (CPU 直結 x4 / CPU 直結 x2 / チップセット経由) の違いが RAID0 の性能にどう効くかを、
同じ条件で単体構成と RAID0 構成を測って確かめるために作った。

## 必要なもの

- Linux、`fio` (3.x、io_uring 対応)、`nvme-cli`、`uv`
- 生デバイスの計測・ページキャッシュの破棄・SMART の取得には `sudo -n` で実行できる権限が要る
  (`/etc/sudoers.d/` に計測中だけ置く許可の例は [docs/sudoers-example](docs/sudoers-example))

## 使い方

```sh
uv run nvme-bench --help
uv run nvme-bench run --help

# btrfs 上のファイル (計測用のサブボリュームを作り、64GiB のファイルを作り直してから測る)
uv run nvme-bench run --label single --suite cdm --target fs

# 未使用の生デバイス (中身は消える。--allow-destroy で明示しないと書き込まない)
uv run nvme-bench run --label single --suite cdm --target nvme0 --allow-destroy /dev/nvme0n1

# 3台同時 (RAID0 で出せる上限の見積もり)
uv run nvme-bench run --label single --suite concurrent --target fs --target nvme0 --target nvme2 \
  --allow-destroy /dev/nvme0n1 --allow-destroy /dev/nvme2n1

# モデルファイルをキャッシュの無い状態から読む
uv run nvme-bench run --label single --suite coldread --target gguf

# 比較 (1つ目が倍率の基準)
uv run nvme-bench compare runs/single runs/raid0
```

計測条件 (対象・suite・各 test の fio オプション) は [configs/default.yaml](configs/default.yaml) にある。
`--runtime` / `--repeats` / `--size` などで defaults を上書きできる。

## 出力

`runs/<label>/` に以下を保存する。

| ファイル | 内容 |
|---|---|
| `results.jsonl` | 1回の計測ごとに1行 (帯域・IOPS・レイテンシ・最高温度・SMART の温度カウンタの前後・fio のコマンド) |
| `fio/*.json` | fio の JSON 出力そのまま |
| `temps/*.json` | 計測中の NVMe 温度の時系列 (1秒ごと) |
| `bwlog/*` | 持続書き込みの1秒ごとの帯域 (sustained のみ) |
| `env.md` | 計測環境 (`scripts/collect-env.sh`)。PCIe の接続経路と上流のリンクも含む |
| `config-*.yaml` | 実行時の実効設定 |
| `run.log` | 日時付きのログ |

## 計測の注意

- 未書き込み (TRIM 済み) の領域を読むと、SSD は NAND を読まずにゼロを返すため異常に速く出る。
  生デバイスは計測範囲を先に書き埋め、ファイルは計測のたびに作り直している。
- btrfs は CoW のため、ランダム書き込みでファイルが断片化する。読み込みの計測を先に、書き込みを後に流す。
- シーケンシャル書き込みは SLC キャッシュの残量で結果が変わる。短時間の計測 (cdm) と、
  キャッシュを使い切るまで書く計測 (sustained) を分けている。

## 結果

計測環境: ASRock X870 Taichi Creator / Ryzen 9 9950X3D / Ubuntu 26.04.1 (カーネル 7.0) / Crucial T500 2TB ×3 / fio 3.41。
詳細は [runs/single/env.md](runs/single/env.md)。

### 単体構成 (`runs/single/`)

| デバイス | 接続 | SEQ1M Q8T1 読み | SEQ1M Q8T1 書き | RND4K Q32T1 読み |
|---|---|---:|---:|---:|
| nvme1 (btrfs 上のファイル) | CPU 直結 Gen4 x4 | 6,756 MB/s | 2,012 MB/s | 1,475 MB/s |
| nvme0 (生デバイス) | チップセット経由 Gen4 x4 | 6,618 MB/s | 6,239 MB/s | 2,157 MB/s |
| nvme2 (生デバイス) | CPU 直結 Gen4 **x2** (USB4 とレーン共有) | 3,552 MB/s | 3,360 MB/s | 2,191 MB/s |
| 3台同時 (SEQ1M Q32T4) | | 15,727 MB/s | 12,807 MB/s | |

- 3台を同時に動かしても各台が単体と同じ速度を出し、チップセット・CPU 側の共有帯域による律速は見られない。
- 54.8GB の GGUF をキャッシュの無い状態から読むと約 11 秒 (read() で 5.2GB/s、mmap で 4.9GB/s)。

### btrfs RAID0 (`runs/raid0/`)

3台を `btrfs device add` → `balance -dconvert=raid0 -mconvert=raid1` で RAID0 化した後、同じ条件で計測した。

| test | 単体 (nvme1) | RAID0 (3台) | 倍率 |
|---|---:|---:|---:|
| SEQ1M Q32T4 read | 6,239 MB/s | 10,630 MB/s | ×1.70 |
| SEQ1M Q8T1 read | 6,756 MB/s | 9,733 MB/s | ×1.44 |
| SEQ1M Q1T1 read | 4,002 MB/s | 6,581 MB/s | ×1.64 |
| RND4K Q32T1 read | 1,475 MB/s | 1,293 MB/s | ×0.88 |
| SEQ1M Q8T1 write | 2,012 MB/s | 1,907 MB/s | ×0.95 |
| RND4K Q32T1 write | 140 MB/s | 179 MB/s | ×1.27 |
| GGUF 54.8GB: O_DIRECT Q32T4 | 12.5 秒 | 5.4 秒 | ×2.35 |
| GGUF 54.8GB: read() 1スレッド | 10.6 秒 | 9.9 秒 | ×1.07 |
| GGUF 54.8GB: mmap 1スレッド | 11.1 秒 | 11.2 秒 | ×0.99 |
| GGUF 54.8GB: read() 8スレッド | - | 6.2 秒 | |

- シーケンシャル読み込みの上限は、最も遅い nvme2 (x2, 3.55GB/s) × 3 ≈ 10.6GB/s の予想どおり。btrfs RAID0 は各台に均等に割り振るため、速いドライブの余力は使われない。
- **1スレッドの read() / mmap は RAID0 にしても速くならない** (約 5GB/s で頭打ち)。ストレージではなく、読み手1本の処理が律速。
  並列に読むか O_DIRECT で深いキューを積めば RAID0 の帯域が出る (llama.cpp b11718 では `--load-mode dio` がある)。
- シーケンシャル書き込みは単体・RAID0 とも約 2GB/s で変わらない。生デバイス単体 (6.2GB/s) より大幅に低く、btrfs 側の書き込み経路が律速と見られる (原因は未確認)。

注意: fio の mmap エンジンは numjobs > 1 だと `offset_increment` が効かず、全ジョブが同じ範囲を読む。
fio の報告は 28GB/s のように物理的にありえない値になるが、実際にディスクから読むのは 1/numjobs。
[scripts/verify_mmap.py](scripts/verify_mmap.py) で `/proc/diskstats` と突き合わせて確認した ([runs/raid0/verify-mmap.log](runs/raid0/verify-mmap.log))。

### btrfs RAID0、M2_2 を x4 に (`runs/raid0-x4/`)

BIOS で USB4 を無効にし、M2_2 を Gen4 x4 にした後、同じ条件で計測した (再起動で NVMe の番号が入れ替わったため、env.md のシリアル番号以外の情報で対応を取っている)。

| test | 単体 | RAID0 (x2 あり) | RAID0 (全台 x4) | 単体比 |
|---|---:|---:|---:|---:|
| SEQ1M Q32T4 read | 6,239 MB/s | 10,630 MB/s | **18,771 MB/s** | ×3.01 |
| SEQ1M Q8T1 read | 6,756 MB/s | 9,733 MB/s | 11,699 MB/s | ×1.73 |
| SEQ1M Q1T1 read | 4,002 MB/s | 6,581 MB/s | 9,863 MB/s | ×2.46 |
| SEQ1M Q8T1 write | 2,012 MB/s | 1,907 MB/s | 2,667 MB/s | ×1.33 |
| GGUF 54.8GB: O_DIRECT Q32T4 | 12.5 秒 | 5.4 秒 | **4.3 秒** | ×2.94 |
| GGUF 54.8GB: read() 1スレッド | 10.6 秒 | 9.9 秒 | 8.8 秒 | ×1.21 |
| GGUF 54.8GB: mmap 1スレッド | 11.1 秒 | 11.2 秒 | 9.9 秒 | ×1.12 |
| GGUF 54.8GB: read() 4スレッド | - | 6.4 秒 | 4.6 秒 | |

- シーケンシャル読み込みは 3台 × 6.2GB/s ≈ 18.7GB/s に到達した。M2_2 の最高温度は 66°C → 74°C に上がった (スロットリングは無し)。

### btrfs の書き込みが遅い原因 (`runs/raid0-x4-write/`)

**データのチェックサムを持つファイルへの O_DIRECT 書き込みは、btrfs がバッファ書き込みにフォールバックする**
(upstream commit `968f19c5b1b7` "btrfs: always fallback to buffered write if the inode requires checksum"。6.6 / 6.12 の stable にもバックポート)。
CrystalDiskMark 相当の書き込み (O_DIRECT) が約 2GB/s に留まるのはこのため。

[scripts/check-dio-fallback.sh](scripts/check-dio-fallback.sh) で、O_DIRECT で 8GiB 書く間に Dirty にされたページを数えると:

| ファイル | Dirty にされたページ |
|---|---:|
| 通常 (データのチェックサムあり) | 8,200 MiB 分 (= 全量がページキャッシュ経由) |
| `chattr +C` (NOCOW = NODATASUM) | 0 MiB |

同じ RAID0 上で、チェックサムあり (fs) となし (fs_nocow) を比べた結果 (MB/s、3回の中央値):

| test | fs | fs_nocow | 倍率 |
|---|---:|---:|---:|
| SEQ1M Q8T1 write (O_DIRECT) | 2,632 | 12,584 | ×4.8 |
| SEQ1M Q32T4 write (O_DIRECT) | 2,433 | 13,444 | ×5.5 |
| SEQ1M Q32T4 write、4ファイル (O_DIRECT) | 3,218 | 11,974 | ×3.7 |
| バッファ書き込み 32GiB + fsync、1ファイル | 3,867 | 4,071 | ×1.05 |
| バッファ書き込み 32GiB + fsync、4ファイル | 7,428 | 8,780 | ×1.18 |
| SEQ1M Q32T4 read (O_DIRECT) | 18,507 | 17,656 | ×0.95 |
| read() 1スレッド (キャッシュなし) | 6,537 | 6,909 | ×1.06 |

- 普通のアプリ (ダウンロード・コピー) が使うバッファ書き込みでは、チェックサムの有無の差は 5〜18% と小さい。
  1ファイルの書き込みは書き手1本の CPU (100%) が律速で、ファイルを分けて並列にすると伸びる。
- O_DIRECT で書くアプリ (DB、`cache=none` の VM イメージなど) は、置き場所のディレクトリに `chattr +C` を付けると約5倍になる。
  代わりにデータのチェックサム (破損の検出)・圧縮・reflink が効かなくなる。
- フォールバックせずにチェックサムを保つ修正 (`IOMAP_DIO_BOUNCE`、ゼロコピーの約95%) は 2026-06 時点で btrfs 側が未マージ。

## ライセンス

MIT
