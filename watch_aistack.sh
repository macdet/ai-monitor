tail -f history/monitor_history.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    d = json.loads(line)
    print(f'{d[\"timestamp\"]} | {d.get(\"state\",{}).get(\"label\",\"-\")} | gpu={d.get(\"gpu_use\",\"-\")}% | vram={d.get(\"vram_percent\",\"-\")}% | power={d.get(\"power_w\",\"-\")}W | temp={d.get(\"gpu_temp\",\"-\")}°C')
"
