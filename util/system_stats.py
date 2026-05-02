from __future__ import annotations

import os
import subprocess
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemStats:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    temp_celsius: float
    uptime_seconds: int
    load_average: tuple[float, float, float]


def get_system_stats() -> SystemStats:
    """
    Collects comprehensive system statistics using standard Linux tools.
    """
    try:
        # CPU usage using /proc/stat
        def cpu_percent() -> float:
            def read_stat():
                with open("/proc/stat") as f:
                    parts = f.readline().split()
                idle, total = int(parts[4]), sum(int(x) for x in parts[1:])
                return idle, total
            
            i1, t1 = read_stat()
            time.sleep(0.5)
            i2, t2 = read_stat()
            return round(100 * (1 - (i2 - i1) / (t2 - t1)), 1)
        
        # Memory usage using /proc/meminfo
        def mem_percent() -> float:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    if line.strip():
                        key, value = line.split(':', 1)
                        meminfo[key] = int(value.strip().split()[0])
            
            used = meminfo["MemTotal"] - meminfo["MemAvailable"]
            return round(100 * used / meminfo["MemTotal"], 1)
        
        # Disk usage using df command
        def disk_percent() -> float:
            result = subprocess.run(['df', '-h', '/'], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                # Extract percentage from the output (last column, remove %)
                output_lines = result.stdout.strip().split('\n')
                if len(output_lines) > 1:
                    disk_line = output_lines[1]
                    percentage = disk_line.split()[-2]  # Get last column
                    return float(percentage.rstrip('%'))
            return 0.0
        
        # Temperature using /sys/class/thermal or hwmon
        def cpu_temp() -> float:
            # Try different temperature sources
            temp_files = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
                "/sys/class/hwmon/hwmon1/temp1_input"
            ]
            
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        with open(temp_file) as f:
                            temp = int(f.read().strip())
                            return temp / 1000.0  # Convert from millidegrees to degrees
                    except Exception:
                        continue
            return 0.0
        
        # Uptime from /proc/uptime
        def uptime_seconds() -> int:
            try:
                with open("/proc/uptime") as f:
                    uptime_str = f.read().split()[0]
                    return int(float(uptime_str))
            except Exception:
                return 0
        
        # Load average using /proc/loadavg
        def load_average() -> tuple[float, float, float]:
            try:
                with open("/proc/loadavg") as f:
                    load_str = f.read().split()[:3]
                    return tuple(float(x) for x in load_str)
            except Exception:
                return (0.0, 0.0, 0.0)
        
        # Collect all stats
        return SystemStats(
            cpu_percent=cpu_percent(),
            memory_percent=mem_percent(),
            disk_percent=disk_percent(),
            temp_celsius=cpu_temp(),
            uptime_seconds=uptime_seconds(),
            load_average=load_average()
        )
        
    except Exception as e:
        logger.error("Systemstatistikabfrage fehlgeschlagen: %s", e)
        # Return default values on error
        return SystemStats(
            cpu_percent=0.0,
            memory_percent=0.0,
            disk_percent=0.0,
            temp_celsius=0.0,
            uptime_seconds=0,
            load_average=(0.0, 0.0, 0.0)
        )


def get_system_stats_json() -> dict[str, Any]:
    """
    Returns system stats as a JSON-compatible dictionary.
    """
    stats = get_system_stats()
    return {
        "cpu_percent": stats.cpu_percent,
        "memory_percent": stats.memory_percent,
        "disk_percent": stats.disk_percent,
        "temp_celsius": stats.temp_celsius,
        "uptime_seconds": stats.uptime_seconds,
        "load_average": stats.load_average,
    }


def apply_action_policy() -> None:
    """
    Applies action policy to system state and thermal decisions.
    This function is a placeholder that would normally process system actions.
    """
    # This is currently just a placeholder since we're testing the system_stats specifically
    pass