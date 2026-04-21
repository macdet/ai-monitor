from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque


@dataclass(slots=True)
class ThermalDecision:
    state: str                  # ok | warn | critical | unknown
    temperature_c: float | None
    should_warn: bool
    should_unload: bool
    reason: str | None


class ThermalPolicy:
    """
    Bewertet Temperaturwerte mit Hysterese statt sofort hektisch zu reagieren.

    Standardlogik:
      - warn ab 85°C
      - critical ab 90°C
      - unload erst nach 3 kritischen Messungen in Folge
      - Rückkehr zu ok erst unter 80°C
    """

    def __init__(
        self,
        warn_temp_c: float = 85.0,
        critical_temp_c: float = 90.0,
        recover_temp_c: float = 80.0,
        critical_hits_needed: int = 3,
        history_size: int = 5,
    ) -> None:
        self.warn_temp_c = warn_temp_c
        self.critical_temp_c = critical_temp_c
        self.recover_temp_c = recover_temp_c
        self.critical_hits_needed = critical_hits_needed
        self.temps: Deque[float] = deque(maxlen=history_size)
        self.states: Deque[str] = deque(maxlen=history_size)
        self._latched_hot = False

    @staticmethod
    def _pick_temperature(stats: dict[str, float | None]) -> float | None:
        edge = stats.get("temperature_edge")
        hotspot = stats.get("temperature_hotspot")
        values = [t for t in (edge, hotspot) if isinstance(t, (float, int))]
        return float(max(values)) if values else None

    def evaluate(self, stats: dict[str, float | None]) -> ThermalDecision:
        current = self._pick_temperature(stats)

        if current is None:
            self.states.append("unknown")
            return ThermalDecision(
                state="unknown",
                temperature_c=None,
                should_warn=True,
                should_unload=False,
                reason="Keine GPU-Temperatur verfügbar",
            )

        self.temps.append(current)

        # Hysterese: nach heißem Zustand erst unter recover wieder "ok"
        if self._latched_hot and current > self.recover_temp_c:
            state = "warn" if current < self.critical_temp_c else "critical"
        elif current >= self.critical_temp_c:
            state = "critical"
            self._latched_hot = True
        elif current >= self.warn_temp_c:
            state = "warn"
            self._latched_hot = True
        else:
            state = "ok"
            self._latched_hot = False

        self.states.append(state)

        critical_hits = sum(
            1 for s in list(self.states)[-self.critical_hits_needed:] if s == "critical"
        )
        should_unload = critical_hits >= self.critical_hits_needed

        if state == "critical":
            reason = f"GPU kritisch heiß: {current:.1f} °C"
        elif state == "warn":
            reason = f"GPU erhöht: {current:.1f} °C"
        else:
            reason = None

        return ThermalDecision(
            state=state,
            temperature_c=current,
            should_warn=(state in {"warn", "critical", "unknown"}),
            should_unload=should_unload,
            reason=reason,
        )
