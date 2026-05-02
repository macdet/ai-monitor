#!/usr/bin/env python3

import subprocess
import json

# Testdaten generieren
test_amd_output = """
temp        : 51.00 C
busy        : 60 %
VRAM        : 1024 / 2048 MiB
"""

test_ollama_status = {
    "status": "ok",
    "models": [
        {"name": "llama2", "modified_at": "2024-04-25T10:00:00Z", "size": 30},  
        {"name": "mistral", "modified_at": "2024-04-25T11:00:00Z", "size": 20}
    ]
}

# Parsing-Test
print("=== Test AMD-SMI Parsing ===")
result = parse_amd_smi(test_amd_output)
print(f"Ergebnis: {result}")
print(f"Gültig: {isinstance(result, dict) and 'gpu_temp' in result and 'vram_used' in result}")

# Status-Test
print("\n=== Test Ollama-Status ===")
print(f"Erwartet: {test_ollama_status}")
print(f"Gültig: {get_ollama_status() is not None}")

# JSONL-Test
print("\n=== Test JSONL Schreiben ===")
write_jsonl({"test": "data"}, "/tmp/test.jsonl")
with open("/tmp/test.jsonl") as f:
    print(f"Erzeugt: {''.join(f.readlines())}")