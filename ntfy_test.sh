cd /mnt/ai-bulk/projects/ai-monitor
source .env
curl -H "Authorization: Bearer $NTFY_TOKEN" \
     -d "Test von ai-monitor" \
     $NTFY_URL/$NTFY_TOPIC
