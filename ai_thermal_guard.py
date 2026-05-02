#!/usr/bin/env python3
"""
ai_thermal_guard.py

Lokaler Schutzmonitor für AMD-GPU + Ollama.
Ziel: Nicht erst auf Hardware-Notabschaltung warten, sondern bei harter Dauerlast
kontrolliert warnen, Modell entladen und Cooldown erzwingen.

Start:
  python3 ai_thermal_guard.py --once --dry-run
  python3 ai_thermal_guard.py --interval 10
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path("/mnt/ai-bulk/projects/ai-monitor")
HISTORY_FILE = BASE_DIR / "history" / "thermal_guard.jsonl"
STATE_FILE = BASE_DIR / "state" / "thermal_guard_state.json"


@dataclasses.dataclass
class GpuStats:
    ok: bool
    source: str = "sysfs"
    error: Optional[str] = None
    card: Optional[str] = None
    edge_c: Optional[float] = None
    hotspot_c: Optional[float] = None
    mem_c: Optional[float] = None
    gpu_use_pct: Optional[float] = None
    power_w: Optional[float] = None
    power_cap_w: Optional[float] = None
    fan_rpm: Optional[int] = None
    fan_pct: Optional[float] = None
    vram_used_mb: Optional[int] = None
    vram_total_mb: Optional[int] = None

    @property
    def vram_ratio(self) -> Optional[float]:
        if self.vram_used_mb is None or not self.vram_total_mb:
            return None
        return self.vram_used_mb / self.vram_total_mb

    @property
    def power_ratio(self) -> Optional[float]:
        if self.power_w is None or not self.power_cap_w:
            return None
        return self.power_w / self.power_cap_w


@dataclasses.dataclass
class OllamaModel:
    name: str
    size_mb: Optional[int] = None
    size_vram_mb: Optional[int] = None
    expires_at: Optional[str] = None

    @property
    def cpu_offload_suspected(self) -> Optional[bool]:
        if self.size_mb is None or self.size_vram_mb is None:
            return None
        return self.size_vram_mb + 512 < self.size_mb


@dataclasses.dataclass
class Decision:
    state: str
    load_state: str
    action: str
    reason: str
    should_warn: bool = False
    should_unload: bool = False
    should_stop_ollama: bool = False


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_int(path: Path) -> Optional[int]:
    txt = read_text(path)
    if txt is None or txt == "":
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def read_float_scaled(path: Path, scale: float) -> Optional[float]:
    val = read_int(path)
    if val is None:
        return None
    return val / scale


def find_amd_card_device() -> Optional[Path]:
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        device = Path(card) / "device"
        vendor = read_text(device / "vendor")
        if vendor and vendor.lower() == "0x1002":
            return device
    return None


def map_temperatures(hwmon: Path) -> Dict[str, float]:
    raw: Dict[str, float] = {}
    fallback_by_index: Dict[int, float] = {}

    for path in sorted(hwmon.glob("temp*_input")):
        stem = path.name.replace("_input", "")
        idx_txt = stem.replace("temp", "")
        if not idx_txt.isdigit():
            continue

        idx = int(idx_txt)
        temp_c = read_float_scaled(path, 1000.0)
        if temp_c is None:
            continue

        fallback_by_index[idx] = temp_c
        label = read_text(hwmon / f"temp{idx}_label")
        label_norm = (label or "").lower()

        if "edge" in label_norm:
            raw["edge_c"] = temp_c
        elif "junction" in label_norm or "hotspot" in label_norm or "hot spot" in label_norm:
            raw["hotspot_c"] = temp_c
        elif "mem" in label_norm or "vram" in label_norm:
            raw["mem_c"] = temp_c

    raw.setdefault("edge_c", fallback_by_index.get(1))
    raw.setdefault("hotspot_c", fallback_by_index.get(2))
    raw.setdefault("mem_c", fallback_by_index.get(3))
    return raw


def read_gpu_sysfs() -> GpuStats:
    device = find_amd_card_device()
    if device is None:
        return GpuStats(ok=False, error="Keine AMD-GPU unter /sys/class/drm/card*/device gefunden")

    stats = GpuStats(ok=True, card=str(device))
    stats.gpu_use_pct = read_float_scaled(device / "gpu_busy_percent", 1.0)

    used = read_int(device / "mem_info_vram_used")
    total = read_int(device / "mem_info_vram_total")
    if used is not None:
        stats.vram_used_mb = int(used / 1024 / 1024)
    if total is not None:
        stats.vram_total_mb = int(total / 1024 / 1024)

    hwmons = sorted((device / "hwmon").glob("hwmon*"))
    if not hwmons:
        stats.error = "Kein hwmon-Verzeichnis gefunden"
        return stats

    def score_hwmon(h: Path) -> int:
        keys = ["temp1_input", "power1_average", "fan1_input", "pwm1"]
        return sum(1 for k in keys if (h / k).exists())

    hwmon = sorted(hwmons, key=score_hwmon, reverse=True)[0]
    temps = map_temperatures(hwmon)
    stats.edge_c = temps.get("edge_c")
    stats.hotspot_c = temps.get("hotspot_c")
    stats.mem_c = temps.get("mem_c")

    stats.power_w = read_float_scaled(hwmon / "power1_average", 1_000_000.0)
    stats.power_cap_w = read_float_scaled(hwmon / "power1_cap", 1_000_000.0)

    fan_rpm = read_int(hwmon / "fan1_input")
    if fan_rpm is not None:
        stats.fan_rpm = fan_rpm

    pwm = read_int(hwmon / "pwm1")
    if pwm is not None:
        stats.fan_pct = round((pwm / 255.0) * 100.0, 1)

    return stats


def ollama_json(path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 3.0) -> Dict[str, Any]:
    url = f"http://127.0.0.1:11434{path}"
    data = None
    headers = {"Content-Type": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        if not body.strip():
            return {}
        return json.loads(body)


def list_ollama_models() -> Tuple[List[OllamaModel], Optional[str]]:
    try:
        data = ollama_json("/api/ps")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return [], f"Ollama /api/ps nicht erreichbar: {exc}"

    result: List[OllamaModel] = []
    for item in data.get("models", []) or []:
        name = item.get("name") or item.get("model")
        if not name:
            continue
        size = item.get("size")
        size_vram = item.get("size_vram") or item.get("size_vram_bytes")
        result.append(
            OllamaModel(
                name=str(name),
                size_mb=int(size / 1024 / 1024) if isinstance(size, (int, float)) else None,
                size_vram_mb=int(size_vram / 1024 / 1024) if isinstance(size_vram, (int, float)) else None,
                expires_at=item.get("expires_at"),
            )
        )
    return result, None


def unload_model(model: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, f"DRY-RUN: würde Modell entladen: {model}"

    try:
        ollama_json("/api/generate", {"model": model, "prompt": "", "keep_alive": 0, "stream": False}, timeout=20)
        return True, f"Modell entladen: {model}"
    except Exception as exc:
        return False, f"Fehler beim Entladen von {model}: {exc}"


def stop_ollama_container(dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "DRY-RUN: würde Docker-Container ollama stoppen"

    try:
        proc = subprocess.run(
            ["docker", "stop", "ollama"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            return True, "Docker-Container ollama gestoppt"
        return False, f"docker stop ollama fehlgeschlagen: {proc.stderr.strip() or proc.stdout.strip()}"
    except Exception as exc:
        return False, f"Fehler bei docker stop ollama: {exc}"


def load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_FILE)


def mark_since(state: Dict[str, Any], key: str, condition: bool, ts: float) -> Optional[float]:
    if condition:
        if key not in state or state[key] is None:
            state[key] = ts
        return ts - float(state[key])
    state[key] = None
    return None


def get_load_state(gpu: GpuStats) -> str:
    use = gpu.gpu_use_pct or 0.0
    power = gpu.power_w or 0.0

    if use >= 80 or power >= 240:
        return "active_high"
    if use >= 40 or power >= 120:
        return "active_medium"
    if use >= 10 or power >= 50:
        return "active_low"
    return "idle"


def decide(gpu: GpuStats, state: Dict[str, Any], args: argparse.Namespace, ts: float) -> Decision:
    if not gpu.ok:
        return Decision("UNKNOWN", "unknown", "none", gpu.error or "GPU-Daten nicht verfügbar", should_warn=True)

    load_state = get_load_state(gpu)
    hotspot = gpu.hotspot_c
    mem = gpu.mem_c
    power_ratio = gpu.power_ratio

    hotspot_num = hotspot if hotspot is not None else -999.0
    mem_num = mem if mem is not None else -999.0
    power_ratio_num = power_ratio if power_ratio is not None else 0.0

    cooldown_until = float(state.get("cooldown_until") or 0.0)
    if ts < cooldown_until:
        release_ok = (
            hotspot is not None
            and hotspot < args.release_hotspot
            and (gpu.power_w is None or gpu.power_w < args.release_power)
        )
        release_duration = mark_since(state, "release_since", release_ok, ts)
        if release_duration is not None and release_duration >= args.release_duration:
            state["cooldown_until"] = 0.0
            state["release_since"] = None
        else:
            return Decision(
                "COOLDOWN",
                load_state,
                "block_new_jobs",
                f"Cooldown aktiv bis {dt.datetime.fromtimestamp(cooldown_until).astimezone().isoformat(timespec='seconds')}",
                should_warn=True,
            )

    if hotspot is not None and hotspot >= args.emergency_hotspot:
        state["cooldown_until"] = ts + args.cooldown
        return Decision(
            "EMERGENCY",
            load_state,
            "stop_ollama",
            f"Hotspot {hotspot:.0f}C >= Emergency {args.emergency_hotspot:.0f}C",
            should_warn=True,
            should_unload=True,
            should_stop_ollama=True,
        )

    if mem is not None and mem >= args.emergency_mem:
        state["cooldown_until"] = ts + args.cooldown
        return Decision(
            "EMERGENCY",
            load_state,
            "stop_ollama",
            f"Memory {mem:.0f}C >= Emergency {args.emergency_mem:.0f}C",
            should_warn=True,
            should_unload=True,
            should_stop_ollama=True,
        )

    hard_dur = mark_since(
        state,
        "hard_since",
        (hotspot is not None and hotspot >= args.hard_hotspot) or (mem is not None and mem >= args.hard_mem),
        ts,
    )
    soft_dur = mark_since(
        state,
        "soft_since",
        (hotspot is not None and hotspot >= args.soft_hotspot) or (mem is not None and mem >= args.soft_mem),
        ts,
    )
    warn_dur = mark_since(
        state,
        "warn_since",
        (hotspot is not None and hotspot >= args.warn_hotspot) or (mem is not None and mem >= args.warn_mem),
        ts,
    )
    power_dur = mark_since(
        state,
        "power_since",
        power_ratio_num >= args.power_warn_ratio and load_state in ("active_medium", "active_high"),
        ts,
    )

    if hard_dur is not None and hard_dur >= args.hard_duration:
        state["cooldown_until"] = ts + args.cooldown
        return Decision(
            "HARD_THROTTLE",
            load_state,
            "unload_model",
            f"Hard-Grenze seit {hard_dur:.0f}s erreicht: hotspot={hotspot}C mem={mem}C",
            should_warn=True,
            should_unload=True,
        )

    if soft_dur is not None and soft_dur >= args.soft_duration:
        return Decision(
            "SOFT_THROTTLE",
            load_state,
            "block_new_jobs",
            f"Soft-Grenze seit {soft_dur:.0f}s erreicht: hotspot={hotspot}C mem={mem}C",
            should_warn=True,
        )

    if warn_dur is not None and warn_dur >= args.warn_duration:
        return Decision(
            "WARN",
            load_state,
            "notify",
            f"Warn-Grenze seit {warn_dur:.0f}s erreicht: hotspot={hotspot}C mem={mem}C",
            should_warn=True,
        )

    if power_dur is not None and power_dur >= args.power_warn_duration:
        return Decision(
            "WARN",
            load_state,
            "notify",
            f"Power seit {power_dur:.0f}s hoch: ratio={power_ratio_num:.0%}",
            should_warn=True,
        )

    if load_state in ("active_medium", "active_high") and (
        hotspot_num >= args.warm_hotspot or mem_num >= args.warm_mem
    ):
        return Decision(
            "WARM",
            load_state,
            "none",
            f"Aktive Last, aber unter Warnschwelle: hotspot={hotspot}C mem={mem}C",
        )

    return Decision("OK", load_state, "none", "Alle Werte unter Policy-Schwellen")


def append_history(payload: Dict[str, Any]) -> None:
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def fmt_temp(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.0f}C"


def fmt_pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.1f}%"


def fmt_w(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.0f}W"


def print_report(gpu: GpuStats, models: List[OllamaModel], decision: Decision, action_messages: List[str], args: argparse.Namespace) -> None:
    print("\n== ai-thermal-guard ==")
    print(now_iso())

    print("\n== Ollama ==")
    if models:
        for m in models:
            size = f"{m.size_mb/1024:.2f}GiB" if m.size_mb else "n/a"
            vram = f"{m.size_vram_mb/1024:.2f}GiB" if m.size_vram_mb else "n/a"
            offload = m.cpu_offload_suspected
            offload_txt = "yes" if offload else "no" if offload is False else "unknown"
            print(f"{m.name} size={size} vram={vram} cpu_offload={offload_txt} expires={m.expires_at or 'n/a'}")
    else:
        print("kein geladenes Modell erkannt")

    print("\n== GPU ==")
    print(
        "use={use} vram={vram} edge={edge} hotspot={hotspot} mem={mem} "
        "power={power}/{cap} power_ratio={pr} fan={fan_pct} {fan_rpm}".format(
            use=fmt_pct(gpu.gpu_use_pct),
            vram="n/a" if gpu.vram_ratio is None else f"{gpu.vram_ratio*100:.2f}%",
            edge=fmt_temp(gpu.edge_c),
            hotspot=fmt_temp(gpu.hotspot_c),
            mem=fmt_temp(gpu.mem_c),
            power=fmt_w(gpu.power_w),
            cap=fmt_w(gpu.power_cap_w),
            pr="n/a" if gpu.power_ratio is None else f"{gpu.power_ratio*100:.1f}%",
            fan_pct=fmt_pct(gpu.fan_pct),
            fan_rpm="n/a" if gpu.fan_rpm is None else f"{gpu.fan_rpm}rpm",
        )
    )
    if gpu.vram_used_mb is not None and gpu.vram_total_mb is not None:
        print(f"vram_mb: used={gpu.vram_used_mb}MB free={gpu.vram_total_mb-gpu.vram_used_mb}MB total={gpu.vram_total_mb}MB")

    print("\n== Policy ==")
    print(
        f"WARM hotspot>={args.warm_hotspot:.0f}C/mem>={args.warm_mem:.0f}C | "
        f"WARN hotspot>={args.warn_hotspot:.0f}C/{args.warn_duration:.0f}s mem>={args.warn_mem:.0f}C/{args.warn_duration:.0f}s | "
        f"SOFT hotspot>={args.soft_hotspot:.0f}C/{args.soft_duration:.0f}s | "
        f"HARD hotspot>={args.hard_hotspot:.0f}C/{args.hard_duration:.0f}s | "
        f"EMERGENCY hotspot>={args.emergency_hotspot:.0f}C"
    )

    print("\n== Bewertung ==")
    print(f"LOAD_STATE: {decision.load_state}")
    print(f"STATE: {decision.state}")
    print(f"ACTION: {decision.action}")
    print(f"REASON: {decision.reason}")

    if action_messages:
        print("\n== Aktionen ==")
        for msg in action_messages:
            print(f"- {msg}")

    if args.dry_run:
        print("\nDRY-RUN aktiv: Es wurden keine destruktiven Aktionen ausgeführt.")


def maybe_notify_ntfy(decision: Decision, gpu: GpuStats, args: argparse.Namespace) -> None:
    if not args.ntfy_url or not decision.should_warn:
        return

    title = f"AI Monitor: {decision.state}"
    msg = (
        f"{decision.reason}\n"
        f"hotspot={fmt_temp(gpu.hotspot_c)} mem={fmt_temp(gpu.mem_c)} "
        f"power={fmt_w(gpu.power_w)} load={decision.load_state}"
    )
    if args.dry_run:
        print(f"DRY-RUN: würde ntfy senden: {title} / {msg}")
        return

    try:
        req = urllib.request.Request(
            args.ntfy_url,
            data=msg.encode("utf-8"),
            headers={"Title": title, "Priority": "urgent" if decision.state in ("HARD_THROTTLE", "EMERGENCY") else "default"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).read()
    except Exception as exc:
        print(f"WARN: ntfy fehlgeschlagen: {exc}", file=sys.stderr)


def run_once(args: argparse.Namespace) -> None:
    ensure_dirs()
    state = load_state()
    ts = time.time()

    gpu = read_gpu_sysfs()
    models, ollama_error = list_ollama_models()
    decision = decide(gpu, state, args, ts)

    action_messages: List[str] = []

    if decision.should_unload and models:
        for m in models:
            ok, msg = unload_model(m.name, args.dry_run)
            action_messages.append(msg)
    elif decision.should_unload and not models:
        action_messages.append("Kein geladenes Ollama-Modell zum Entladen gefunden")

    if decision.should_stop_ollama:
        if args.allow_stop_container:
            ok, msg = stop_ollama_container(args.dry_run)
            action_messages.append(msg)
        else:
            action_messages.append("Emergency erreicht, aber docker stop ist deaktiviert. Nutze --allow-stop-container zum Aktivieren.")

    if ollama_error:
        action_messages.append(ollama_error)

    payload = {
        "ts": now_iso(),
        "gpu": dataclasses.asdict(gpu),
        "ollama": [dataclasses.asdict(m) for m in models],
        "decision": dataclasses.asdict(decision),
        "actions": action_messages,
        "dry_run": args.dry_run,
    }
    append_history(payload)
    save_state(state)

    print_report(gpu, models, decision, action_messages, args)
    maybe_notify_ntfy(decision, gpu, args)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AMD GPU + Ollama Thermal Guard")

    p.add_argument("--once", action="store_true", help="Nur einmal messen und beenden")
    p.add_argument("--interval", type=float, default=10.0, help="Messintervall in Sekunden")
    p.add_argument("--dry-run", action="store_true", help="Keine Aktionen ausführen, nur anzeigen")
    p.add_argument("--allow-stop-container", action="store_true", help="Bei EMERGENCY Docker-Container ollama stoppen")
    p.add_argument("--ntfy-url", default=os.environ.get("AI_MONITOR_NTFY_URL"), help="Optionaler ntfy Topic URL")

    p.add_argument("--warm-hotspot", type=float, default=80.0)
    p.add_argument("--warm-mem", type=float, default=80.0)

    p.add_argument("--warn-hotspot", type=float, default=88.0)
    p.add_argument("--warn-mem", type=float, default=88.0)
    p.add_argument("--warn-duration", type=float, default=60.0)

    p.add_argument("--soft-hotspot", type=float, default=92.0)
    p.add_argument("--soft-mem", type=float, default=92.0)
    p.add_argument("--soft-duration", type=float, default=60.0)

    p.add_argument("--hard-hotspot", type=float, default=95.0)
    p.add_argument("--hard-mem", type=float, default=96.0)
    p.add_argument("--hard-duration", type=float, default=30.0)

    p.add_argument("--emergency-hotspot", type=float, default=100.0)
    p.add_argument("--emergency-mem", type=float, default=100.0)

    p.add_argument("--power-warn-ratio", type=float, default=0.90)
    p.add_argument("--power-warn-duration", type=float, default=120.0)

    p.add_argument("--cooldown", type=float, default=300.0)
    p.add_argument("--release-hotspot", type=float, default=80.0)
    p.add_argument("--release-power", type=float, default=80.0)
    p.add_argument("--release-duration", type=float, default=120.0)

    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.once:
        run_once(args)
        return 0

    print("ai-thermal-guard gestartet. Abbruch mit Ctrl+C.")
    print(f"Intervall: {args.interval}s")
    if args.dry_run:
        print("DRY-RUN aktiv.")

    while True:
        try:
            run_once(args)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nBeendet.")
            return 0
        except Exception as exc:
            print(f"ERROR: Monitor-Schleife abgefangen: {exc}", file=sys.stderr)
            time.sleep(max(5.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
