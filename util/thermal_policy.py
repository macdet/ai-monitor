from __future__ import annotations

import json
import logging
import math
import subprocess
from collections import deque
from dataclasses import dataclass
from typing import Deque

log = logging.getLogger(__name__)


def _safe_float(value: object) -> float | None:
    """Convert a value to float, returning None for missing or invalid input."""
    if isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_valid_temp(value: object) -> bool:
    """True for finite int/float values (bool excluded)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


@dataclass(slots=True)
class GpuTemps:
    edge: float | None
    hotspot: float | None
    mem: float | None


@dataclass(slots=True)
class ThermalDecision:
    state: str                  # ok | warn | critical | unknown
    temperature_c: float | None
    temps_raw: GpuTemps | None
    should_warn: bool
    should_unload: bool
    reason: str | None


class ThermalPolicy:
    """
    Bewertet GPU-Temperaturen mit Hysterese.

    Für die Schutzlogik zählt konservativ der höchste verfügbare Wert aus:
    - edge
    - hotspot / junction
    - memory

    Standard:
      - warn      >= 85 °C
      - critical  >= 95 °C
      - unload    nach N kritischen Messungen in Folge
      - recover   erst unter recover_temp_c zurück zu ok
    """

    def __init__(
        self,
        warn_temp_c: float = 85.0,
        critical_temp_c: float = 95.0,
        recover_temp_c: float = 75.0,
        critical_hits_needed: int = 3,
        history_size: int = 3,
        gpu_index: int = 0,
        unknown_hits_needed: int = 5,
        **_: object,
    ) -> None:
        # **_ hält alte/zusätzliche Parameter kompatibel, z. B.
        # warn_hotspot_c, warn_mem_c, critical_hotspot_c, critical_mem_c.

        if critical_hits_needed < 1:
            raise ValueError("critical_hits_needed muss >= 1 sein")
        if history_size < critical_hits_needed:
            raise ValueError(
                f"history_size ({history_size}) muss >= critical_hits_needed ({critical_hits_needed}) sein"
            )
        if not (recover_temp_c < warn_temp_c < critical_temp_c):
            raise ValueError(
                f"Es muss gelten: recover_temp_c < warn_temp_c < critical_temp_c "
                f"({recover_temp_c} < {warn_temp_c} < {critical_temp_c})"
            )

        self.warn_temp_c = warn_temp_c
        self.critical_temp_c = critical_temp_c
        self.recover_temp_c = recover_temp_c
        self.critical_hits_needed = critical_hits_needed
        self.history_size = history_size
        self.gpu_index = gpu_index
        self.unknown_hits_needed = unknown_hits_needed

        self.temps: Deque[float] = deque(maxlen=history_size)
        self.states: Deque[str] = deque(maxlen=history_size)

        self._latched_hot = False
        self._consecutive_unknown = 0

    def _read_amd_smi(self) -> GpuTemps:
        """
        Fallback: liest Temperatur per amd-smi JSON.

        Der produktive monitor.py sollte bevorzugt die Werte aus get_gpu_stats()
        übergeben, weil diese bei dir bereits zuverlässig edge/hotspot/mem liefern.
        """
        try:
            raw = subprocess.check_output(
                [
                    "amd-smi", "metric",
                    "-g", str(self.gpu_index),
                    "-t", "--json",
                ],
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.error("amd-smi nicht gefunden")
            return GpuTemps(edge=None, hotspot=None, mem=None)
        except subprocess.TimeoutExpired:
            log.warning("amd-smi timeout (GPU %d)", self.gpu_index)
            return GpuTemps(edge=None, hotspot=None, mem=None)
        except subprocess.CalledProcessError as exc:
            log.warning("amd-smi exit %d (GPU %d)", exc.returncode, self.gpu_index)
            return GpuTemps(edge=None, hotspot=None, mem=None)

        try:
            data = json.loads(raw)
            gpu_entry = next(
                (gpu for gpu in data["gpu_data"] if gpu.get("gpu") == self.gpu_index),
                None,
            )
            if gpu_entry is None:
                log.warning("amd-smi: GPU %d nicht in Ausgabe", self.gpu_index)
                return GpuTemps(edge=None, hotspot=None, mem=None)

            temp = gpu_entry["temperature"]
            return GpuTemps(
                edge=_safe_float(temp.get("edge", {}).get("value")),
                hotspot=_safe_float(temp.get("hotspot", {}).get("value")),
                mem=_safe_float(temp.get("mem", {}).get("value")),
            )
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            log.warning("amd-smi Parse-Fehler: %s", exc)
            return GpuTemps(edge=None, hotspot=None, mem=None)

    @staticmethod
    def _pick_temperature(temps: GpuTemps) -> float | None:
        """
        Konservativ: höchste verfügbare Temperatur verwenden.

        Damit wird ein Zustand wie edge=63°C, hotspot=95°C korrekt als 95°C
        bewertet und nicht fälschlich als unkritisch.
        """
        values = [float(temp) for temp in (temps.edge, temps.hotspot, temps.mem) if _is_valid_temp(temp)]
        return max(values) if values else None

    def evaluate(
        self,
        temperature_c: float | None = None,
        temps_raw: GpuTemps | None = None,
    ) -> ThermalDecision:
        """
        Bewertet die aktuelle Temperatur.

        temperature_c:
          Optional bereits berechneter Regelwert, z. B. max(edge, hotspot, mem).

        temps_raw:
          Optionale Rohwerte für Logging/Reason.
        """
        raw = temps_raw if temps_raw is not None else self._read_amd_smi()
        current = (
            temperature_c
            if _is_valid_temp(temperature_c)
            else self._pick_temperature(raw)
        )

        if current is None:
            self._consecutive_unknown += 1
            self.states.append("unknown")
            noisy = self._consecutive_unknown >= self.unknown_hits_needed

            return ThermalDecision(
                state="unknown",
                temperature_c=None,
                temps_raw=raw,
                should_warn=noisy,
                should_unload=False,
                reason=(
                    f"Keine GPU-Temperatur ({self._consecutive_unknown}×)"
                    if noisy else None
                ),
            )

        self._consecutive_unknown = 0
        self.temps.append(float(current))

        if self._latched_hot and current > self.recover_temp_c:
            state = "warn" if current < self.critical_temp_c else "critical"
        elif current >= self.critical_temp_c:
            state = "critical"
            self._latched_hot = True
        elif current >= self.warn_temp_c:
            state = "warn"
        else:
            state = "ok"
            self._latched_hot = False

        self.states.append(state)

        log.debug(
            "thermal current=%.1f°C edge=%s hotspot=%s mem=%s state=%s latch=%s history=%s",
            current,
            f"{raw.edge:.1f}°C" if raw and raw.edge is not None else "–",
            f"{raw.hotspot:.1f}°C" if raw and raw.hotspot is not None else "–",
            f"{raw.mem:.1f}°C" if raw and raw.mem is not None else "–",
            state,
            self._latched_hot,
            list(self.states),
        )

        if state == "critical":
            parts = [f"GPU kritisch heiß: thermal={current:.1f} °C"]
            if raw.edge is not None:
                parts.append(f"edge={raw.edge:.1f} °C")
            if raw.hotspot is not None:
                parts.append(f"hotspot={raw.hotspot:.1f} °C")
            if raw.mem is not None:
                parts.append(f"mem={raw.mem:.1f} °C")
            reason = " ".join(parts)
        elif state == "warn":
            parts = [f"GPU erhöhte Temperatur: thermal={current:.1f} °C"]
            if raw.edge is not None:
                parts.append(f"edge={raw.edge:.1f} °C")
            if raw.hotspot is not None:
                parts.append(f"hotspot={raw.hotspot:.1f} °C")
            if raw.mem is not None:
                parts.append(f"mem={raw.mem:.1f} °C")
            reason = " ".join(parts)
        else:
            reason = None

        should_unload = (
            self._latched_hot
            and len(self.states) >= self.critical_hits_needed
            and all(state == "critical" for state in self.states)
        )

        return ThermalDecision(
            state=state,
            temperature_c=current,
            temps_raw=raw,
            should_warn=(state in {"warn", "critical"}),
            should_unload=should_unload,
            reason=reason,
        )
