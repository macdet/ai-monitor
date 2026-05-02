#!/usr/bin/env bash
set -u

GPU="${1:-0}"
INTERVAL="${2:-2}"

OUT_DIR="/mnt/ai-bulk/projects/ai-monitor/history"
OUT_FILE="$OUT_DIR/amd_smi_gpu_watch.jsonl"

mkdir -p "$OUT_DIR"

command -v amd-smi >/dev/null 2>&1 || {
  echo "FEHLER: amd-smi nicht gefunden"
  exit 1
}

command -v jq >/dev/null 2>&1 || {
  echo "FEHLER: jq fehlt. Installieren mit:"
  echo "sudo apt install -y jq"
  exit 1
}

echo "GPU-Watch gestartet"
echo "GPU: $GPU"
echo "Intervall: ${INTERVAL}s"
echo "Logdatei: $OUT_FILE"
echo "Abbruch mit Strg+C"

while true; do
  ts="$(date -Is)"

  metric_json="$(amd-smi metric -g "$GPU" -m -u -p -c -t --json 2>/tmp/amd_smi_metric.err || true)"
  process_json="$(amd-smi process -g "$GPU" --json 2>/tmp/amd_smi_process.err || true)"

  metric_ok=false
  process_ok=false

  echo "$metric_json" | jq -e . >/dev/null 2>&1 && metric_ok=true
  echo "$process_json" | jq -e . >/dev/null 2>&1 && process_ok=true

  if [[ "$metric_ok" == "true" ]]; then
    metric_payload="$metric_json"
  else
    metric_payload="$(jq -n \
      --arg raw "$metric_json" \
      --arg err "$(cat /tmp/amd_smi_metric.err 2>/dev/null)" \
      '{parse_error: true, raw: $raw, stderr: $err}')"
  fi

  if [[ "$process_ok" == "true" ]]; then
    process_payload="$process_json"
  else
    process_payload="$(jq -n \
      --arg raw "$process_json" \
      --arg err "$(cat /tmp/amd_smi_process.err 2>/dev/null)" \
      '{parse_error: true, raw: $raw, stderr: $err}')"
  fi

  jq -cn \
    --arg ts "$ts" \
    --arg gpu "$GPU" \
    --argjson metric "$metric_payload" \
    --argjson process "$process_payload" \
    '{
      ts: $ts,
      gpu: $gpu,
      metric: $metric,
      process: $process
    }' >> "$OUT_FILE"

  sleep "$INTERVAL"
done
