#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from typing import Any


DOCKER_BIN = "/usr/bin/docker"


UNIT_FACTORS: dict[str, int] = {
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
}


def parse_percent(value: object) -> float | None:
    text = str(value or "").strip().replace("%", "")
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def parse_size_to_bytes(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None

    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)$", text)
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).lower()
    factor = UNIT_FACTORS.get(unit)

    if factor is None:
        return None

    return int(number * factor)


def parse_usage_limit_pair(value: object) -> dict[str, int | None | str]:
    text = str(value or "").strip()

    if "/" not in text:
        return {
            "used_bytes": None,
            "limit_bytes": None,
            "raw": text,
        }

    used_raw, limit_raw = [part.strip() for part in text.split("/", 1)]

    return {
        "used_bytes": parse_size_to_bytes(used_raw),
        "limit_bytes": parse_size_to_bytes(limit_raw),
        "raw": text,
    }


def parse_io_pair(value: object) -> dict[str, int | None | str]:
    text = str(value or "").strip()

    if "/" not in text:
        return {
            "read_bytes": None,
            "write_bytes": None,
            "raw": text,
        }

    read_raw, write_raw = [part.strip() for part in text.split("/", 1)]

    return {
        "read_bytes": parse_size_to_bytes(read_raw),
        "write_bytes": parse_size_to_bytes(write_raw),
        "raw": text,
    }


def parse_pids(value: object) -> int | None:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return None


def normalize_container_stats(raw: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    mem = parse_usage_limit_pair(raw.get("MemUsage"))
    net = parse_io_pair(raw.get("NetIO"))
    block = parse_io_pair(raw.get("BlockIO"))

    return {
        "id": raw.get("ID"),
        "name": raw.get("Name") or raw.get("Container") or fallback_name,
        "container": raw.get("Container"),
        "cpu_percent": parse_percent(raw.get("CPUPerc")),
        "mem_percent": parse_percent(raw.get("MemPerc")),
        "mem_usage_raw": raw.get("MemUsage"),
        "mem_used_bytes": mem["used_bytes"],
        "mem_limit_bytes": mem["limit_bytes"],
        "net_io_raw": raw.get("NetIO"),
        "net_rx_bytes": net["read_bytes"],
        "net_tx_bytes": net["write_bytes"],
        "block_io_raw": raw.get("BlockIO"),
        "block_read_bytes": block["read_bytes"],
        "block_write_bytes": block["write_bytes"],
        "pids": parse_pids(raw.get("PIDs")),
        "docker_error": None,
    }


def collect_container_stats(container_name: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [
                DOCKER_BIN,
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                container_name,
            ],
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0:
            return {
                "name": container_name,
                "docker_error": f"docker_stats_failed rc={proc.returncode}: {stderr}",
            }

        if not stdout:
            return {
                "name": container_name,
                "docker_error": "docker_stats_empty_output",
            }

        first_line = stdout.splitlines()[0]
        raw = json.loads(first_line)

        if not isinstance(raw, dict):
            return {
                "name": container_name,
                "docker_error": f"unexpected_docker_stats_type: {type(raw).__name__}",
            }

        return normalize_container_stats(raw, fallback_name=container_name)

    except Exception as exc:
        return {
            "name": container_name,
            "docker_error": f"docker_stats_exception: {exc!r}",
        }


def collect_docker_stats(
    container_names: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if container_names is None:
        container_names = ["ollama"]

    return {
        container_name: collect_container_stats(container_name)
        for container_name in container_names
    }


def get_docker_stats(
    container_names: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return collect_docker_stats(container_names)


def collect() -> dict[str, Any]:
    return collect_docker_stats(["ollama"])


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, ensure_ascii=False))