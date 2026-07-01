"""
Revenue Alert — daily cron sender.
Generates alert and sends via WhatsApp bridge.
"""
import subprocess
import requests

SCRIPT = "/var/www/difotoin-dashboard/scripts/revenue_alert.py"
VENV = "/var/www/difotoin-dashboard/nicegui_template/.venv/bin/python3"
BRIDGE = "http://localhost:3000/send"

RECIPIENTS = ["6285714166666@s.whatsapp.net"]
# NOVI: "6285697055924@s.whatsapp.net"

def send_wa(cid, msg):
    try:
        r = requests.post(BRIDGE, json={"chatId": cid, "message": msg}, timeout=15)
        return r.json().get("success")
    except Exception as e:
        print("Send error:", e)
        return False

result = subprocess.run([VENV, SCRIPT], capture_output=True, text=True, timeout=120)
msg = result.stdout.strip()
print(msg)

for cid in RECIPIENTS:
    ok = send_wa(cid, msg)
    status = "OK" if ok else "FAIL"
    print("{}: {}".format(cid, status))
