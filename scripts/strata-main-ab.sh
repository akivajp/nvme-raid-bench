#!/usr/bin/env bash
# Strata main (O_DIRECT パッチ入り) で、既定の読み込みと STRATA_UNBUFFERED_LOAD=1 を交互に測り、チェックサムも比べる。
# 起動・停止は ~/llm-lab/strata/main-odirect.sh。cold は posix_fadvise DONTNEED で GGUF のページキャッシュだけを捨てる。
# 結果: runs/strata-main-odirect/ab.tsv (モード、起動〜health の秒、最初の応答の秒、エンジンの読み込み行)
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,4p' "$0"; exit 0 ;; esac
OUT="$(cd "$(dirname "$0")/.." && pwd)/runs/strata-main-odirect"
CTL="${HOME}/llm-lab/strata/main-odirect.sh"
GGUF="${HOME}/llm-lab/gguf/Qwen3.8-Flash-Next-GSQ-RCO/IQ3_S"
KEY=bench-local-key-0123456789
drop() { python3 -c 'import os,sys
for f in sys.argv[1:]:
    fd=os.open(f,os.O_RDONLY); os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED); os.close(fd)' "$GGUF"/*.gguf; }
one() {  # $1 = ラベル、残りはコンテナの環境変数
  local label=$1; shift
  "$CTL" down; sync; drop
  local t0; t0=$(date +%s.%N)
  "$CTL" up "$@"
  until curl -fs http://127.0.0.1:18082/health >/dev/null 2>&1; do sleep 0.5; done
  local t1; t1=$(date +%s.%N)
  curl -fs -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' http://127.0.0.1:18082/v1/chat/completions \
    -d '{"model":"qwen3.8-flash-next-iq3_s","messages":[{"role":"user","content":"Say hello."}],"max_tokens":8,"temperature":0}' >/dev/null
  local t2; t2=$(date +%s.%N)
  local eng; eng=$(docker exec llmb-strata-main sh -c 'grep -hE "expert arena (read|checksum)|loaded [0-9.]+ GiB at" /data/state/strata/launch/docker.engine.log | tail -3' | tr '\n' '|')
  printf '%s\t%.1f\t%.1f\t%s\n' "$label" "$(echo "$t1-$t0" | bc)" "$(echo "$t2-$t1" | bc)" "$eng" | tee -a "$OUT/ab.tsv"
}
trap '"$CTL" down' EXIT
for i in 1 2 3; do
  one default
  one direct STRATA_UNBUFFERED_LOAD=1
done
one verify-default STRATA_VERIFY_ARENA=1
one verify-direct STRATA_UNBUFFERED_LOAD=1 STRATA_VERIFY_ARENA=1
