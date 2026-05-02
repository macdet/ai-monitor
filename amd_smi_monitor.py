#!/usr/bin/env python3

import subprocess
import json
import argparse
from datetime import datetime
from typing import Dict, Any
import sys

class AmdSmiMonitor:
    def __init__(self, gpu_id: int = 0, rocm_smi_path: str = "/opt/rocm/bin/rocm-smi"):
        self.gpu_id = gpu_id
        self.rocm_smi_path = rocm_smi_path
        
    def _create_error_metrics(self, error_msg: str) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "gpu_id": self.gpu_id,
            "metrics": {
                "error": error_msg,
                "status": "error"
            }
        }
        
    def get_gpu_metrics(self) -> Dict[str, Any]:
        """Holt die GPU-Metriken mit amd-smi"""
        try:
            # Führe den Befehl aus, um alle Metriken abzurufen
            cmd = [
                self.rocm_smi_path,
                'metric',
                '-g', str(self.gpu_id),
                '--json'
            ]
            
            # Prüfe zuerst, ob der Befehl existiert
            try:
                subprocess.run(['which', self.rocm_smi_path], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                error_msg = f"rocm-smi-Befehl nicht gefunden: {self.rocm_smi_path}"
                print(f"Fehler: {error_msg}")
                return self._create_error_metrics(error_msg)
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse die JSON-Ausgabe
            data = json.loads(result.stdout)
            
            # Transformiere die Daten für bessere Verarbeitung
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'gpu_id': self.gpu_id,
                'metrics': {}
            }
            
            # Prüfe, ob die Ausgabe gültig ist
            if not data or 'gpu_data' not in data:
                error_msg = "Ungültige oder leere JSON-Ausgabe von amd-smi"
                print(f"Fehler: {error_msg}")
                return self._create_error_metrics(error_msg)
            
            # Verarbeite die Datenstruktur, die von amd-smi zurückgegeben wird
            if 'gpu_data' in data and len(data['gpu_data']) > 0:
                gpu_info = data['gpu_data'][0]
                
                # Speicherauslastung
                if 'mem_usage' in gpu_info:
                    mem_info = gpu_info['mem_usage']
                    metrics['metrics']['memory'] = {
                        'total_vram': mem_info.get('total_vram', {}).get('value'),
                        'used_vram': mem_info.get('used_vram', {}).get('value'),
                        'free_vram': mem_info.get('free_vram', {}).get('value'),
                        'used_percentage': round((mem_info.get('used_vram', {}).get('value', 0) / 
                                                mem_info.get('total_vram', {}).get('value', 1)) * 100, 2)
                    }
                
                # Leistung
                if 'power' in gpu_info:
                    power_info = gpu_info['power']
                    metrics['metrics']['power'] = {
                        'socket_power': power_info.get('socket_power', {}).get('value'),
                        'throttle_status': power_info.get('throttle_status')
                    }
                
                # Temperatur
                if 'temperature' in gpu_info:
                    temp_info = gpu_info['temperature']
                    metrics['metrics']['temperature'] = {
                        'edge': temp_info.get('edge', {}).get('value'),
                        'hotspot': temp_info.get('hotspot', {}).get('value'),
                        'mem': temp_info.get('mem', {}).get('value')
                    }
                
                # Frequenzen
                if 'clock' in gpu_info:
                    clock_info = gpu_info['clock']
                    gfx_clk = clock_info.get('gfx_0', {}).get('clk', {}).get('value')
                    mem_clk = clock_info.get('mem_0', {}).get('clk', {}).get('value')
                    metrics['metrics']['clock'] = {
                        'gfx_clock': gfx_clk,
                        'memory_clock': mem_clk
                    }
                
                # Usage
                if 'usage' in gpu_info:
                    usage_info = gpu_info['usage']
                    metrics['metrics']['engine'] = {
                        'gfx_activity': usage_info.get('gfx_activity', {}).get('value'),
                        'umc_activity': usage_info.get('umc_activity', {}).get('value')
                    }
            
            return metrics
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Fehler bei der Ausführung von amd-smi: {e}"
            print(f"Fehler: {error_msg}")
            # Überprüfe, ob der Fehler auf Berechtigungsprobleme zurückzuführen ist
            if "Permission denied" in str(e) or "permission" in str(e).lower():
                print("\nWARNUNG: Zugriffsrechte auf GPU fehlen!")
                print("Bitte führen Sie folgende Befehle aus:")
                print("sudo usermod -aG render $USER")
                print("Dann melden Sie sich ab und wieder an.")
            elif "No such file or directory" in str(e):
                print("\nFEHLER: rocm-smi nicht gefunden!")
                print("Bitte stellen Sie sicher, dass ROCm korrekt installiert ist.")
            return self._create_error_metrics(error_msg)
        except Exception as e:
            error_msg = f"Fehler bei der Datenverarbeitung: {e}"
            print(f"Fehler: {error_msg}")
            return self._create_error_metrics(error_msg)

def main():
    parser = argparse.ArgumentParser(description='GPU Monitoring mit amd-smi')
    parser.add_argument('--single', action='store_true', help='Führt eine einzelne Abfrage aus')
    parser.add_argument('--gpu', type=int, default=0, help='GPU-ID (Standard: 0)')
    
    args = parser.parse_args()
    
    monitor = AmdSmiMonitor(gpu_id=args.gpu)
    
    if args.single:
        metrics = monitor.get_gpu_metrics()
        print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()