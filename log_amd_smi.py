#!/usr/bin/env python3

import subprocess
from datetime import datetime
import json

def run_amd_smi_command():
    try:
        # Ausführung des Befehls und Erfassen der JSON-Ausgabe
        result = subprocess.run(
            ["amd-smi", "metric", "-g", "0", "-m", "-u", "-p", "-c", "-t", "--json"],
            capture_output=True,
            text=True,
            check=True
        )
           
        # Parse die JSON-Ausgabe (sollte bereits im JSON-Format vorliegen)
        json_data = result.stdout
   
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Ausführen des Befehls: {e}")
        return None
    except Exception as e:
        print(f"Ein unbekannter Fehler ist aufgetreten: {e}")
        return None
       
    return json_data
      
def log_metrics_to_file(json_data):
    try:
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "metrics": json.loads(json_data)
        }
         
        # Log-Datei öffnen und den Metrik-Eintrag schreiben
        with open("amd_smi_history.log", "a") as f:
            f.write(json.dumps(log_entry, indent=2))
            f.write("\n")
           
    except Exception as e:
        print(f"Fehler beim Schreiben in die Logdatei: {e}")
     
def main():
    json_data = run_amd_smi_command()
    if json_data:
        log_metrics_to_file(json_data)
   
if __name__ == "__main__":
    main()