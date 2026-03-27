#!/usr/bin/env bash
set -euo pipefail

cd /Users/carl/Desktop/Logicgap

for mode in m1 m2 m3; do
  echo "=== START ${mode} $(date '+%Y-%m-%d %H:%M:%S') ==="
  if [[ "$mode" == "m3" ]]; then
    env PYTHONUNBUFFERED=1 .venv/bin/python scripts/run_logicgap_ablation_replay.py \
      --mode m3 \
      --datasets general_dataset complex_dataset \
      --task-results-root results \
      --results-root results \
      --output-prefix deepseek \
      --model deepseek-chat \
      --api-url https://api.deepseek.com/v1 \
      --request-timeout 180 \
      --max-retries 2 \
      --m3-success-attempts 1 \
      --m3-fail-attempts 5
  else
    env PYTHONUNBUFFERED=1 .venv/bin/python scripts/run_logicgap_ablation_replay.py \
      --mode "$mode" \
      --datasets general_dataset complex_dataset \
      --task-results-root results \
      --results-root results \
      --output-prefix deepseek \
      --model deepseek-chat \
      --api-url https://api.deepseek.com/v1 \
      --request-timeout 180 \
      --max-retries 2 \
      --max-attempts 3
  fi
  echo "=== END ${mode} $(date '+%Y-%m-%d %H:%M:%S') ==="
done
