from dataclasses import dataclass
from typing import Any


@dataclass
class AlertEvent:
    """Repräsentiert ein zu meldendes Ereignis."""
    level: str        # warn | critical
    category: str     # thermal | gpu | ollama | docker
    message: str
    once: bool        # True = nur bei Zustandswechsel senden


@dataclass
class SystemState:
    """Minimaler Zustand für die Policy-Evaluation."""
    gpu: Any
    ollama_models: list[Any]
    ollama_hanging: bool
    docker_containers: list[dict]


class AlertPolicy:
    """Zentrale Alert-Logik, getrennt vom Monitor-Loop."""

    def __init__(
        self,
        cpu_fallback_threshold: float = 20.0,
        vram_leak_threshold: float = 2.0,
        ollama_timeout: float = 3.0,
    ):
        self.cpu_fallback_threshold = cpu_fallback_threshold
        self.vram_leak_threshold = vram_leak_threshold
        self.ollama_timeout = ollama_timeout
        self._last_states: dict[str, bool] = {}

    def evaluate(self, state: SystemState) -> list[AlertEvent]:
        alerts: list[AlertEvent] = []

        # 1. ALERT_CPU_FALLBACK
        fallback_active = any(
            getattr(m, "cpu_pct", 0) > self.cpu_fallback_threshold
            for m in state.ollama_models
        )
        if fallback_active:
            if not self._last_states.get("cpu_fallback", False):
                alerts.append(
                    AlertEvent(
                        level="warn",
                        category="ollama",
                        message="CPU-Fallback erkannt: Modell läuft nicht vollständig auf GPU.",
                        once=True,
                    )
                )
        self._last_states["cpu_fallback"] = fallback_active

        # 2. ALERT_OLLAMA_HANG
        ollama_running = any(
            c.get("name") == "ollama" and c.get("status") == "running"
            for c in state.docker_containers
        )
        if ollama_running and state.ollama_hanging:
            alerts.append(
                AlertEvent(
                    level="critical",
                    category="ollama",
                    message="Ollama hängt: Container läuft, aber API antwortet nicht.",
                    once=False,
                )
            )

        # 3. ALERT_VRAM_LEAK
        vram_used = getattr(state.gpu, "vram_used_gib", 0.0)
        if vram_used is None:
            vram_used = 0.0
        if vram_used > self.vram_leak_threshold and len(state.ollama_models) == 0:
            alerts.append(
                AlertEvent(
                    level="critical",
                    category="gpu",
                    message=f"VRAM-Leak verdächtig: {vram_used:.1f} GiB belegt ohne aktives Modell.",
                    once=False,
                )
            )

        return alerts
