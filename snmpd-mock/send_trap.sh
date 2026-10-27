#!/bin/sh
# Bắn SNMP v2c trap tới collector (input snmptrap).
# Dùng:  docker exec snmpd-mock send_trap.sh <IP_COLLECTOR:PORT> ['<message>'] [user] [action]
# Biến môi trường: COMMUNITY (mặc định cym_ro_2026)
set -e
DEST="$1"
if [ -z "$DEST" ]; then
  echo "Dùng: send_trap.sh <IP_COLLECTOR:PORT> ['<message>'] [user] [action]" >&2
  exit 1
fi
DEFAULT_MSG='{"state":"success","action":"NODE_POST_INFO_1","user":"hoangnx"}'
MSG="${2:-$DEFAULT_MSG}"
USER_NAME="${3:-hoangnx}"
ACTION="${4:-NODE_POST_INFO_1}"
COMMUNITY="${COMMUNITY:-cym_ro_2026}"

# '' = uptime tự lấy; trap OID 1.3.6.1.4.1.99999.0.1; 3 biến: message / user / action
snmptrap -v 2c -c "$COMMUNITY" "$DEST" '' 1.3.6.1.4.1.99999.0.1 \
  1.3.6.1.4.1.99999.2.1 s "$MSG" \
  1.3.6.1.4.1.99999.2.2 s "$USER_NAME" \
  1.3.6.1.4.1.99999.2.3 s "$ACTION"
echo "Da gui trap toi $DEST (community $COMMUNITY)"
