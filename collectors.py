#!/usr/bin/env python3
"""
Collector-Skript für AMD-SMI und Ollama-Monitoring

Erfasst und speichert Metriken in JSONL-Format.
"""

import subprocess
import json
import re
import time
import argparse
from typing import Dict, Optional


def parse_amd_smi(output: str) -> Optional[Dict]:
    """
    Parsed AMD-SMI-Ausgabe und gibt ein Dictionary mit Metriken zurück.
    
    Args:
        output: Rohausgabe von `rocm-smi --showtemp`
    
    Returns:
        Dictionary mit GPU-Metriken oder None bei Fehlern.
        """    
    try:
        # Extrahiere Temperatur und andere relevante Daten
        temp_match = re.search(r'(\d+)\.(\d+) C', output)
        memory_match = re.search(r'VRAM ([\d.]+) / ([\d.]+) MiB', output)
        
        if not temp_match or not memory_match:
            print(f"[WARN] Erwartetes Format nicht in AMD-SMI-Ausgabe gefunden.\n{output}")
            return None
        
        return {
            'gpu_temp': float(f'{temp_match.group(1)}.{temp_match.group(2)}'),
            'vram_used': float(memory_match.group(1)),
            'vram_total': float(memory_match.group(2))
        }
    except Exception as e:
        print(f"[ERROR] Fehler beim Parsen von AMD-SMI: {e}")
        return None


def get_ollama_status() -> Optional[Dict]:
    """
    Ruft den Ollama-Status ab.
    
    Returns:
        Dictionary mit Ollama-Status oder None bei Fehlern.
    """
    try:
        result = subprocess.run(['curl', '-s', 'http://localhost:11434/api/status'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print(f"[WARN] Ollama-Status konnte nicht abgerufen werden: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print("[WARN] Ollama-Status-Timeout (5s)")
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"[ERROR] Fehler beim Parsen von Ollama-Status: {e}")
        return None


def write_jsonl(data: Dict, file_path: str) -> None:
    """
    Schreibt eine Zeile in eine JSONL-Datei.
    
    Args:
        data: Dictionary mit Metriken und Zeitstempel
        file_path: Pfad zur JSONL-Datei
    """
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + '\n')
    except Exception as e:
        print(f"[ERROR] Fehler beim Schreiben in JSONL: {e}")


def main():
    parser = argparse.ArgumentParser(description='AMD-SMI und Ollama Monitoring')
    parser.add_argument('--interval', type=int, default=5, help='Abfrageintervall in Sekunden')
    args = parser.parse_args()
    
    print(f"[INFO] Starte Monitoring mit {args.interval}s-Intervall")
    
    while True:
        timestamp = int(time.time())
        gpu_data = parse_amd_smi(subprocess.check_output(['rocm-smi', '--showtemp'], text=True))
        ollama_data = get_ollama_status()
        
        record = {
            'timestamp': timestamp,
            'gpu_temp': gpu_data.get('gpu_temp') if gpu_data else None,
            'vram_used': gpu_data.get('vram_used') if gpu_data else None,
            'vram_total': gpu_data.get('vram_total') if gpu_data else None,
            'ollama_models': []
        }
        
        if ollama_data:
            record['ollama_models'] = ollama_data.get('models', [])
        
        write_jsonl(record, '/mnt/ai-bulk/projects/ai-monitor/history/monitor_history.jsonl')
        time.sleep(args.interval)


if __name__ == '__main__':
    main()