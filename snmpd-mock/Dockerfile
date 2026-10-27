# SNMP agent giả lập để test input snmp (polling) và snmptrap của CyM-Log-Shipper
FROM alpine:3.20
RUN apk add --no-cache net-snmp net-snmp-tools
COPY snmpd.conf /etc/snmp/snmpd.conf
COPY cym_msg.sh send_trap.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/cym_msg.sh /usr/local/bin/send_trap.sh
EXPOSE 161/udp 161/tcp
# -C: chỉ đọc file -c (không có -C snmpd đọc file 2 lần -> lỗi "Address in use")
CMD ["snmpd", "-f", "-Lo", "-C", "-c", "/etc/snmp/snmpd.conf"]
