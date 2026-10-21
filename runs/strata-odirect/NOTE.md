# 注意

- `model_load.jsonl` の `disk_gb` と `trace-*.json` の読み込み速度は **約 2/3 に過小評価** されている。
  2026-10-21 の再起動でシステムディスクが nvme1n1p1 に変わったのに、計数するデバイス名が古いまま (nvme2n1p1) だったため。
  ロード時間 (`ready_s` / `first_s`) と、Strata 自身のログの読み込み速度には影響しない。
  スクリプトは、以降の計測のためにデバイス名を sysfs から取るよう修正済み。
- cold は `posix_fadvise(POSIX_FADV_DONTNEED)` で、モデルと Strata のデータのファイルのページキャッシュだけを捨てている
  (sudo の一時許可を外した後のため。`runs/model-load*/` は `vm.drop_caches=3`)。
- チェックサムの比較 (`verify-checksum.log`): 本家とパッチ版 (O_DIRECT) で `8ae1446c68dc969b` (46.84 GiB) が一致。
- Strata 自身のログの読み込み速度 (experts loaded):
  - 本家 0.1.45: 5.83 / 5.94 / 5.95 GiB/s
  - パッチ版、既定: 5.81 GiB/s
  - パッチ版、`STRATA_UNBUFFERED_LOAD=1`: 12.04 / 12.11 / 12.15 GiB/s
