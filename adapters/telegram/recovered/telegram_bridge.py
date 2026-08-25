import os
import time
import json
import fcntl
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path("/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes")
HERMES_HOME = BASE / "data"
HERMES = BASE / "hermes.sh"
ENV_FILE = HERMES_HOME / ".env"
OFFSET_FILE = BASE / "telegram.offset"
LOCK_FILE = BASE / "telegram_bridge.lock"

def load_env():
    env = os.environ.copy()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env["HERMES_HOME"] = str(HERMES_HOME)
    return env

ENV = load_env()
TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED = {
    x.strip()
    for x in ENV.get("TELEGRAM_ALLOWED_USERS", "").split(",")
    if x.strip()
}

if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN not configured")
if not ALLOWED:
    raise SystemExit("TELEGRAM_ALLOWED_USERS not configured")

API = f"https://api.telegram.org/bot{TOKEN}"

def telegram(method, data=None, timeout=40):
    payload = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(f"{API}/{method}", data=payload)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def send(chat_id, text):
    text = text or "(Hermes returned empty response)"
    for i in range(0, len(text), 3800):
        telegram(
            "sendMessage",
            {"chat_id": chat_id, "text": text[i:i + 3800]},
            timeout=20,
        )

def ask_hermes(prompt):
    p = subprocess.run(
        [str(HERMES), "-z", prompt],
        env=ENV,
        text=True,
        capture_output=True,
        timeout=300,
    )
    if p.returncode == 0:
        return p.stdout.strip()
    err = p.stderr.strip() or p.stdout.strip()
    return f"Hermes error:\n{err[-3000:]}"

def get_offset():
    try:
        return int(OFFSET_FILE.read_text().strip())
    except Exception:
        return 0

def save_offset(offset):
    OFFSET_FILE.write_text(str(offset))

lock_fp = open(LOCK_FILE, "w")
try:
    fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit("telegram_bridge already running")

offset = get_offset()
print("Telegram -> Hermes bridge started", flush=True)

while True:
    try:
        result = telegram(
            "getUpdates",
            {
                "timeout": 30,
                "offset": offset,
                "allowed_updates": json.dumps(["message"]),
            },
            timeout=40,
        )

        for update in result.get("result", []):
            offset = update["update_id"] + 1
            save_offset(offset)

            message = update.get("message") or {}
            user = message.get("from") or {}
            chat = message.get("chat") or {}

            user_id = str(user.get("id", ""))
            chat_id = chat.get("id")
            text = message.get("text")

            if user_id not in ALLOWED:
                continue

            if not text or not chat_id:
                if chat_id:
                    send(chat_id, "Only text messages are supported for now.")
                continue

            print(f"Message from {user_id}: {text[:100]}", flush=True)

            try:
                answer = ask_hermes(text)
            except subprocess.TimeoutExpired:
                answer = "Hermes execution timed out."
            except Exception as e:
                answer = f"Bridge error: {e}"

            send(chat_id, answer)

    except Exception as e:
        print(f"poll error: {e}", flush=True)
        time.sleep(5)
