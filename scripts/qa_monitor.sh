#!/usr/bin/env bash
# qa_monitor.sh — QA session monitor
# Tails logs from all relevant containers with source prefix.
# Usage: ./scripts/qa_monitor.sh [session_label]
#
# Output → stdout + /tmp/qa_session_<label>_<date>.log
# Stop with Ctrl+C.

set -euo pipefail

LABEL="${1:-session}"
DATE=$(date +%Y%m%d_%H%M%S)
LOGFILE="/tmp/qa_monitor_${LABEL}_${DATE}.log"

echo "[QA-MON] Starting QA monitor | label=$LABEL | log=$LOGFILE"
echo "[QA-MON] Press Ctrl+C to stop"
echo ""

# ── Snapshot: docker ps, network, stats ──────────────────────────────────
echo "=== docker ps ===" | tee -a "$LOGFILE"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

echo "=== docker stats (one shot) ===" | tee -a "$LOGFILE"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | tee -a "$LOGFILE" || echo "(stats unavailable)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

echo "=== network inspect dziki-internal ===" | tee -a "$LOGFILE"
docker network inspect dziki-internal 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for n in d:
    for name,info in n.get('Containers',{}).items():
        print(f\"  {info.get('Name','?')} → {info.get('IPv4Address','?')}\")
" 2>/dev/null | tee -a "$LOGFILE" || echo "(network not found or python unavailable)" | tee -a "$LOGFILE"

echo "=== network inspect dziki-app ===" | tee -a "$LOGFILE"
docker network inspect dziki-app 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for n in d:
    for name,info in n.get('Containers',{}).items():
        print(f\"  {info.get('Name','?')} → {info.get('IPv4Address','?')}\")
" 2>/dev/null | tee -a "$LOGFILE" || echo "(network not found)" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

echo "=== LIVE LOGS (follow) ===" | tee -a "$LOGFILE"

# ── Tail all relevant containers ─────────────────────────────────────────
(docker logs -f --tail=0 dziki-api        2>&1 | sed 's/^/[API]       /' | tee -a "$LOGFILE") &
(docker logs -f --tail=0 dziki-worker-py  2>&1 | sed 's/^/[WORKER-PY] /' | tee -a "$LOGFILE") &
(docker logs -f --tail=0 dziki-celery-beat 2>&1 | sed 's/^/[BEAT]      /' | tee -a "$LOGFILE") &
(docker logs -f --tail=0 dziki-worker-r   2>&1 | sed 's/^/[WORKER-R]  /' | tee -a "$LOGFILE") &
(docker logs -f --tail=0 dziki-frontend   2>&1 | sed 's/^/[FRONTEND]  /' | tee -a "$LOGFILE") &

# Nginx (container may not be running in dev)
if docker ps --format '{{.Names}}' | grep -q dziki-nginx 2>/dev/null; then
  (docker logs -f --tail=0 dziki-nginx 2>&1 | sed 's/^/[NGINX]     /' | tee -a "$LOGFILE") &
fi

PIDS=$(jobs -p)

cleanup() {
  echo ""
  echo "[QA-MON] Stopping... log saved to $LOGFILE"
  kill $PIDS 2>/dev/null || true
  wait 2>/dev/null
  echo "[QA-MON] Lines captured: $(wc -l < "$LOGFILE")"
}

trap cleanup INT TERM EXIT

wait
