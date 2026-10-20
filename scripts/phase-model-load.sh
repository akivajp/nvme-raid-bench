#!/usr/bin/env bash
# LLM サーバーのロード時間の計測 (scripts/model_load.py) を、GPU テナント (asr4u) を止めた状態で流す。
# 終了時 (失敗・Ctrl-C を含む) にはサーバーを止め、GPU テナントを戻す。local-llm-bench のスクリプトを使う。
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,3p' "$0"; echo "usage: $(basename "$0") [model_load.py の引数...]"; exit 0 ;; esac

cd "$(dirname "${BASH_SOURCE[0]}")/.."
LLM_BENCH="${HOME}/ghq/github.com/akivajp/local-llm-bench/scripts"
cleanup() {
  "${LLM_BENCH}/llamacpp.sh" down >/dev/null 2>&1 || true
  STRATA_MODEL=IQ3_S "${LLM_BENCH}/strata.sh" down >/dev/null 2>&1 || true
  "${LLM_BENCH}/gpu-tenant.sh" start || echo "WARNING: GPU テナントの起動確認に失敗" >&2
}
trap cleanup EXIT
"${LLM_BENCH}/gpu-tenant.sh" stop
uv run python scripts/model_load.py "$@"
