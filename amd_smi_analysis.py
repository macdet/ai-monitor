#!/usr/bin/env python3
"""
Analyse-Tool für AMD-SMI-Daten
Verarbeitet die von gpu_watch_amd_smi.sh erzeugten JSON-Dateien
und implementiert Fehlerbehandlung für kritische Werte.
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

def read_jsonl_file(file_path: str) -> List[Dict]:
    """Liest eine JSONL-Datei und gibt eine Liste von JSON-Objekten zurück"""
    data = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
    except Exception as e:
        print(f"Fehler beim Lesen der Datei {file_path}: {e}")
        return []
    return data

def analyze_temperature_data(data: List[Dict]) -> Dict[str, Any]:
    """Analysiert Temperaturdaten und identifiziert kritische Werte"""
    temperatures = {
        'edge': [],
        'hotspot': [],
        'mem': []
    }
    
    # Sammle Temperaturwerte
    for entry in data:
        metric = entry.get('metric', {})
        if not isinstance(metric, dict):
            continue
            
        # Extrahiere Temperaturwerte
        if 'edge' in metric and isinstance(metric['edge'], (int, float)):
            temperatures['edge'].append(metric['edge'])
        if 'hotspot' in metric and isinstance(metric['hotspot'], (int, float)):
            temperatures['hotspot'].append(metric['hotspot'])
        if 'mem' in metric and isinstance(metric['mem'], (int, float)):
            temperatures['mem'].append(metric['mem'])
    
    # Berechne Statistiken
    stats = {}
    for temp_type, values in temperatures.items():
        if values:
            stats[temp_type] = {
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'current': values[-1] if values else None
            }
        else:
            stats[temp_type] = None
    
    # Identifiziere kritische Werte
    critical_alerts = []
    for temp_type, value in stats.items():
        if value and value['current'] is not None:
            # Kritische Temperaturen (Beispielwerte - anpassen nach Bedarf)
            if temp_type == 'edge' and value['current'] > 85:
                critical_alerts.append(f"Kritischer Edge-Temperaturwert: {value['current']}°C")
            elif temp_type == 'hotspot' and value['current'] > 90:
                critical_alerts.append(f"Kritischer Hotspot-Temperaturwert: {value['current']}°C")
            elif temp_type == 'mem' and value['current'] > 95:
                critical_alerts.append(f"Kritischer Mem-Temperaturwert: {value['current']}°C")
    
    return {
        'temperatures': stats,
        'critical_alerts': critical_alerts,
        'total_entries': len(data)
    }

def analyze_gpu_usage(data: List[Dict]) -> Dict[str, Any]:
    """Analysiert GPU-Nutzung und andere Metriken"""
    gpu_stats = {
        'vram_usage': [],
        'gpu_utilization': [],
        'power': [],
        'frequency': []
    }
    
    for entry in data:
        metric = entry.get('metric', {})
        if not isinstance(metric, dict):
            continue
            
        # GPU-Nutzung
        if 'vram_used' in metric and 'vram_total' in metric:
            if metric['vram_total'] > 0:
                usage_percent = (metric['vram_used'] / metric['vram_total']) * 100
                gpu_stats['vram_usage'].append(usage_percent)
        
        if 'gpu' in metric and isinstance(metric['gpu'], (int, float)):
            gpu_stats['gpu_utilization'].append(metric['gpu'])
        
        if 'power' in metric and isinstance(metric['power'], (int, float)):
            gpu_stats['power'].append(metric['power'])
        
        if 'fan' in metric and isinstance(metric['fan'], (int, float)):
            gpu_stats['frequency'].append(metric['fan'])
    
    # Berechne Statistiken
    stats = {}
    for stat_type, values in gpu_stats.items():
        if values:
            stats[stat_type] = {
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'current': values[-1] if values else None
            }
        else:
            stats[stat_type] = None
    
    return stats

def generate_report(data: List[Dict]) -> str:
    """Erstellt einen Bericht basierend auf den analysierten Daten"""
    if not data:
        return "Keine Daten zum Analysieren vorhanden"
    
    # Temperaturanalyse
    temp_analysis = analyze_temperature_data(data)
    gpu_analysis = analyze_gpu_usage(data)
    
    report = []
    report.append("=" * 50)
    report.append("AMD-SMI ANALYSE BERICHTE")
    report.append("=" * 50)
    report.append(f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Gesamt Einträge: {temp_analysis['total_entries']}")
    report.append("")
    
    report.append("TEMPERATUR ANALYSIS:")
    report.append("-" * 30)
    for temp_type, values in temp_analysis['temperatures'].items():
        if values:
            report.append(f"{temp_type.capitalize()}:")
            report.append(f"  Min: {values['min']:.1f}°C")
            report.append(f"  Max: {values['max']:.1f}°C")
            report.append(f"  Durchschnitt: {values['avg']:.1f}°C")
            report.append(f"  Aktuell: {values['current']:.1f}°C")
        else:
            report.append(f"{temp_type.capitalize()}: Keine Daten verfügbar")
    
    report.append("")
    report.append("GPU NUTZUNG:")
    report.append("-" * 30)
    for stat_type, values in gpu_analysis.items():
        if values:
            report.append(f"{stat_type.capitalize()}:")
            report.append(f"  Min: {values['min']:.1f}")
            report.append(f"  Max: {values['max']:.1f}")
            report.append(f"  Durchschnitt: {values['avg']:.1f}")
            report.append(f"  Aktuell: {values['current']:.1f}")
        else:
            report.append(f"{stat_type.capitalize()}: Keine Daten verfügbar")
    
    if temp_analysis['critical_alerts']:
        report.append("")
        report.append("KRITISCHE ALARME:")
        report.append("-" * 30)
        for alert in temp_analysis['critical_alerts']:
            report.append(f"⚠️  {alert}")
    
    report.append("=" * 50)
    
    return "\n".join(report)

def main():
    """Hauptfunktion"""
    if len(sys.argv) < 2:
        print("Verwendung: python3 amd_smi_analysis.py <pfad_zu_jsonl_datei>")
        return
    
    file_path = sys.argv[1]
    
    # Prüfe, ob die Datei existiert
    if not os.path.exists(file_path):
        print(f"Fehler: Datei {file_path} nicht gefunden")
        return
    
    # Lese Daten
    data = read_jsonl_file(file_path)
    
    if not data:
        print("Keine Daten zur Analyse gefunden")
        return
    
    # Generiere Bericht
    report = generate_report(data)
    print(report)
    
    # Speichere Bericht in einer Datei
    report_file = file_path.replace('.jsonl', '_analysis.txt')
    try:
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"Bericht gespeichert in: {report_file}")
    except Exception as e:
        print(f"Fehler beim Speichern des Berichts: {e}")

if __name__ == "__main__":
    main()