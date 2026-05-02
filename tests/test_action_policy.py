import pytest
from unittest.mock import MagicMock

from util.action_policy import ActionPolicy, UnloadModel, RestartContainer, SendAlert, NoOp
from util.alert_policy import AlertEvent, SystemState
from util.thermal_policy import ThermalDecision


@pytest.fixture
def policy():
    return ActionPolicy()


@pytest.fixture
def base_state():
    return SystemState(
        gpu=MagicMock(),
        ollama_models=[],
        ollama_hanging=False,
        docker_containers=[],
    )


@pytest.fixture
def base_thermal():
    return ThermalDecision(
        state="ok",
        temperature_c=60.0,
        temps_raw=None,
        reason=None,
        should_warn=False,
        should_unload=False,
    )


def test_unload_on_thermal_critical(policy, base_state, base_thermal):
    """Regel 1: ThermalDecision.should_unload=True -> UnloadModel"""
    base_thermal.should_unload = True
    actions = policy.evaluate(base_state, base_thermal, [])
    assert any(isinstance(a, UnloadModel) for a in actions)


def test_restart_on_ollama_hang(policy, base_state, base_thermal):
    """Regel 2: AlertEvent level=critical category=ollama -> RestartContainer"""
    alert = AlertEvent(
        level="critical",
        category="ollama",
        message="Ollama hängt: Container läuft, aber API antwortet nicht.",
        once=False,
    )
    actions = policy.evaluate(base_state, base_thermal, [alert], recent_restart_count=2)
    assert any(isinstance(a, RestartContainer) for a in actions)


def test_no_restart_if_too_many_restarts(policy, base_state, base_thermal):
    """Regel 2: Restart nur wenn restart_count < 3"""
    alert = AlertEvent(
        level="critical",
        category="ollama",
        message="Ollama hängt",
        once=False,
    )
    actions = policy.evaluate(base_state, base_thermal, [alert], recent_restart_count=3)
    assert not any(isinstance(a, RestartContainer) for a in actions)


def test_send_alert_on_warn(policy, base_state, base_thermal):
    """Regel 3: AlertEvent -> SendAlert"""
    alert = AlertEvent(
        level="warn",
        category="ollama",
        message="CPU-Fallback erkannt: Modell läuft nicht vollständig auf GPU.",
        once=True,
    )
    actions = policy.evaluate(base_state, base_thermal, [alert])
    assert any(isinstance(a, SendAlert) for a in actions)


def test_noop_when_healthy(policy, base_state, base_thermal):
    """Regel 4: Sonst NoOp"""
    actions = policy.evaluate(base_state, base_thermal, [])
    assert any(isinstance(a, NoOp) for a in actions)
