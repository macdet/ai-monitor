#!/bin/bash
# =============================================================================
# safe_shutdown_proxmox.sh – Geordneter Shutdown für Proxmox + Ollama + VMs + LXC
# =============================================================================
# Hinweis: Als root ausführen. Passt die Timeouts nach Bedarf an.

set -euo pipefail
LOG_TAG="PROXMOX-SHUTDOWN"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

log "🛑 Starte Proxmox Graceful Shutdown Sequence..."

# 1. ✅ Ollama Service stoppen
log "📦 Stoppe Ollama.service..."
systemctl stop ollama.service 2>/dev/null || true
if systemctl is-active --quiet ollama.service; then
    log "⚠️  Ollama läuft noch. Zwangsbeendigung..."
    systemctl kill ollama.service 2>/dev/null || true
    sleep 3
fi
log "✅ Ollama beendet."

# 2. ✅ LXC-Container herunterfahren
log "📦 Fahre LXC-Container geordnet herunter..."
for ctid in $(pct list --status running --noheader 2>/dev/null | awk '{print $2}'); do
    log "  ↳ Shutdown Container $ctid..."
    pct shutdown "$ctid" --timeout 30 2>/dev/null || true
    sleep 2
done

# 3. ✅ VMs herunterfahren
log "📦 Fahre VMs geordnet herunter..."
for vmid in $(qm list --status running --noheader 2>/dev/null | awk '{print $1}'); do
    log "  ↳ Shutdown VM $vmid..."
    qm shutdown "$vmid" --timeout 30 2>/dev/null || true
    sleep 2
done

# 4. ✅ Warten & Sichern
log "💾 Synce Dateisysteme & warte auf Hintergrundprozesse..."
sync
sleep 15

# 5. 🔌 Sauberes Ausschalten
log "🔌 Initiiere System-Poweroff..."
poweroff