#!/bin/sh
# Output của extend cym_msg: 1 dòng JSON, timestamp (ms) lúc collector poll
printf '{"state":"success","action":"NODE_POST_INFO_1","user":"hoangnx","timestamp":%s000}\n' "$(date +%s)"
