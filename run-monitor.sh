#!/usr/bin/env bash
set -euo pipefail
cd /mnt/ai-bulk/projects/ai-monitor
set -a
source .env
set +a
python3 monitor.py
