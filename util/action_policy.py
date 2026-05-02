from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from util.alert_policy import AlertEvent, SystemState
from util.thermal_policy import ThermalDecision


@dataclass
class UnloadModel:
    reason: str


@dataclass
class RestartContainer:
    reason: str


@dataclass
class SendAlert:
    reason: str


@dataclass
class NoOp:
    reason: str


Action = Union[UnloadModel, RestartContainer, SendAlert, NoOp]


class ActionPolicy:
    """Aktor-Logik – trennt Entscheidung von Ausführung.
    
    Rein funktional: Keine internen Zustände oder Seiteneffekte.
    Der Aufrufer (monitor.py) verwaltet Rate-Limits und Historie.
    """

    def evaluate(
        self,
        state: SystemState,
        thermal: ThermalDecision,
        alerts: list[AlertEvent],
        recent_restart_count: int = 0,
    ) -> list[Action]:
        """
        Bewertet den Systemzustand und gibt eine Liste von Aktionen zurück.
        """
        actions: list[Action] = []

        # 1. ThermalDecision.should_unload=True -> UnloadModel
        if thermal.should_unload:
            actions.append(
                UnloadModel(reason="Kritische GPU-Temperatur erreicht, Modell entladen.")
            )

        # 2. AlertEvent level=critical category=ollama -> RestartContainer
        ollama_critical = any(
            a.level == "critical" and a.category == "ollama" for a in alerts
        )
        if ollama_critical and recent_restart_count < 3:
            actions.append(
                RestartContainer(reason="Ollama hängt, Container-Neustart erforderlich.")
            )

        # 3. AlertEvent -> SendAlert
        for alert in alerts:
            actions.append(SendAlert(reason=alert.message))

        # 4. Sonst NoOp
        if not actions:
            actions.append(NoOp(reason="System stabil, keine Aktionen erforderlich."))

        return actions
