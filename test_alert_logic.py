#!/usr/bin/env python3
"""
Test script to debug why alerts are not being sent for homepage container.
This tests the exact logic from monitor.py without try/catch blocks.
"""

from util.ollama_stats import get_ollama_data
from util.docker_stats import get_docker_stats
from util.gpu_stats import get_gpu_stats
from util.alerts import send_ntfy_alerts


def test_monitor_system():
    """Test the complete monitoring logic step by step"""
    print("=== Testing Monitor System Logic ===")

    # 1. Ollama Check
    print("\n1. Testing Ollama Check:")
    ollama = get_ollama_data()
    print(f"Ollama status: {ollama['status']}")
    if ollama["status"] == "ok":
        for m in ollama["models"]:
            print(f"  Model: {m['name']} ({m['processor']}) - Context: {m['context']}")

    # 2. Docker Check
    print("\n2. Testing Docker Check:")
    docker_stats = get_docker_stats()
    alerts = []

    for c in docker_stats:
        print(f"  Container {c['name']}: status={c['status']}, health={c['health']}")

        # This is the EXACT logic from monitor.py
        if c["status"] != "running" or c["health"] == "unhealthy":
            alert_msg = f"🔴 Container {c['name']} ist {c['status']} ({c['health']})"
            print(f"    -> ALERT TRIGGERED: {alert_msg}")
            alerts.append(alert_msg)
        elif c["status"] == "missing":
            alert_msg = f"🔴 Container {c['name']} ist nicht vorhanden (nicht gefunden)"
            print(f"    -> MISSING ALERT TRIGGERED: {alert_msg}")
            alerts.append(alert_msg)

    # 3. GPU Check
    print("\n3. Testing GPU Check:")
    gpu = get_gpu_stats()
    print(
        f"GPU VRAM: {gpu['vram_used']:.2f} / {gpu['vram_total']:.2f} GB ({gpu['vram_ratio']:.1%})"
    )

    if gpu["vram_ratio"] is not None and gpu["vram_ratio"] > 0.95:
        alert_msg = f"🟡 Warnung: GPU VRAM-Verbrauch ist hoch: {gpu['vram_ratio']:.1%}"
        print(f"    -> GPU ALERT TRIGGERED: {alert_msg}")
        alerts.append(alert_msg)

    # 4. Alert Sending
    print("\n4. Testing Alert Sending:")
    print(f"Total alerts to send: {len(alerts)}")
    if alerts:
        print("Attempting to send alerts...")
        success = send_ntfy_alerts(alerts)
        print(f"Alert sending result: {success}")
    else:
        print("No alerts to send")


if __name__ == "__main__":
    test_monitor_system()
