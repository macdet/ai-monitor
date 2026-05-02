import pytest
from dataclasses import dataclass
from util.alert_policy import AlertPolicy, AlertEvent, SystemState


@dataclass
class MockGpu:
    vram_used_gib: float | None


@dataclass
class MockModel:
    name: str
    cpu_pct: float


class TestAlertPolicy:
    def test_cpu_fallback_triggers_on_state_change(self):
        policy = AlertPolicy(cpu_fallback_threshold=20.0)
        state_fallback = SystemState(
            gpu=MockGpu(vram_used_gib=1.0),
            ollama_models=[MockModel(name="llama3", cpu_pct=30.0)],
            ollama_hanging=False,
            docker_containers=[],
        )

        # Erster Aufruf: Zustand wechselt von False -> True
        alerts = policy.evaluate(state_fallback)
        assert len(alerts) == 1
        assert alerts[0].level == "warn"
        assert alerts[0].once is True

        # Zweiter Aufruf: Zustand bleibt True -> kein Alert (once-Logik)
        alerts2 = policy.evaluate(state_fallback)
        assert len(alerts2) == 0

        # Zustand wechselt zu False
        state_ok = SystemState(
            gpu=MockGpu(vram_used_gib=1.0),
            ollama_models=[MockModel(name="llama3", cpu_pct=10.0)],
            ollama_hanging=False,
            docker_containers=[],
        )
        policy.evaluate(state_ok)

        # Zustand wechselt wieder zu True -> Alert wird erneut gesendet
        alerts3 = policy.evaluate(state_fallback)
        assert len(alerts3) == 1

    def test_ollama_hang_triggers(self):
        policy = AlertPolicy()
        state = SystemState(
            gpu=MockGpu(vram_used_gib=1.0),
            ollama_models=[],
            ollama_hanging=True,
            docker_containers=[{"name": "ollama", "status": "running"}],
        )
        alerts = policy.evaluate(state)
        hang_alert = [a for a in alerts if a.category == "ollama" and a.level == "critical"]
        assert len(hang_alert) == 1
        assert hang_alert[0].once is False

    def test_vram_leak_triggers(self):
        policy = AlertPolicy(vram_leak_threshold=2.0)
        state = SystemState(
            gpu=MockGpu(vram_used_gib=3.5),
            ollama_models=[],
            ollama_hanging=False,
            docker_containers=[],
        )
        alerts = policy.evaluate(state)
        leak_alert = [a for a in alerts if a.category == "gpu" and a.level == "critical"]
        assert len(leak_alert) == 1
        assert "VRAM-Leak" in leak_alert[0].message

    def test_no_alerts_when_system_ok(self):
        policy = AlertPolicy()
        state = SystemState(
            gpu=MockGpu(vram_used_gib=1.0),
            ollama_models=[MockModel(name="llama3", cpu_pct=10.0)],
            ollama_hanging=False,
            docker_containers=[],
        )
        alerts = policy.evaluate(state)
        assert len(alerts) == 0

    def test_vram_leak_ignored_when_models_loaded(self):
        policy = AlertPolicy(vram_leak_threshold=2.0)
        state = SystemState(
            gpu=MockGpu(vram_used_gib=3.0),
            ollama_models=[MockModel(name="llama3", cpu_pct=5.0)],
            ollama_hanging=False,
            docker_containers=[],
        )
        alerts = policy.evaluate(state)
        leak_alert = [a for a in alerts if a.category == "gpu"]
        assert len(leak_alert) == 0
