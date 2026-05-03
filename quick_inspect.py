import json, sys

data = json.load(sys.stdin)
for m in data.get('models', []):
    vram = m.get('size_vram', 0) / 1024**3
    total = m.get('size', 0) / 1024**3
    ctx = m.get('context_length', '?')
    quant = m.get('details', {}).get('quantization_level', '?')
    params = m.get('details', {}).get('parameter_size', '?')
    print(f"{m['name']:<30} {params} {quant}  VRAM: {vram:.1f}/{total:.1f} GB  ctx: {ctx}")
