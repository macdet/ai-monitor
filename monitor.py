from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

from util.docker_stats import get_docker_stats
from util.ollama_stats import get_ollama_stats
from util.gpu_stats import get_gpu_stats
from util.alerts import build_alerts, send_ntfy_alerts

logger = logging.getLogger(__name__)


def main() -> int:
    # Basis-Logging, damit Fehler nicht still geschluckt werden.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    stats = {
        "docker": get_docker_stats(),
        "ollama": get_ollama_stats(),
        "gpu": get_gpu_stats(),
    }

    alerts = build_alerts(stats)
    if alerts:
        send_ntfy_alerts(alerts)

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
