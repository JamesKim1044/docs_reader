#!/usr/bin/env bash
# Run a GPU-enabled Ollama server WITHOUT sudo, by launching the snap's bundled
# binary + CUDA libraries OUTSIDE the snap sandbox (which otherwise forces CPU).
# Reuses the models the snap already downloaded. Listens on :11500.
#
#   bash tools/ollama_gpu.sh            # start server (foreground)
#   BENCH_OLLAMA=http://127.0.0.1:11500/v1 python tools/benchmark.py ...
#   docs-reader extract ... --base-url http://127.0.0.1:11500/v1
set -euo pipefail

SNAP=/snap/ollama/current
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11500}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/var/snap/ollama/common/models}"
export LD_LIBRARY_PATH="$SNAP/lib/ollama:$SNAP/lib/ollama/cuda_v12:${LD_LIBRARY_PATH:-}"

echo "Starting GPU Ollama on $OLLAMA_HOST (models: $OLLAMA_MODELS)"
exec "$SNAP/bin/ollama" serve
