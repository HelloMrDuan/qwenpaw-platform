#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import time
import urllib.parse
import urllib.request

BASE = "/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes"
HERMES_HOME = f"{BASE}/data"
ENV_FILE = pathlib.Path(HERMES_HOME) / ".env"
STATE_DIR = pathlib.Path(HERMES_HOME) / "bridge_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
OFFSET_FILE = STATE_DIR / "telegram_offset.txt"
LOG_FILE = pathlib.Path(BASE) / "telegram_bridge.log"
RUNNER = f"{BASE}/run_image_and_reply.sh"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def load_env(path):
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

ENV = load_env(ENV_FILE)
TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN missing in .env")

API = f"https://api.telegram.org/bot{TOKEN}"

def tg_get_updates(offset=None, timeout=30):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    url = API + "/getUpdates?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout + 10) as r:
        return json.loads(r.read().decode("utf-8"))

def tg_send_message(chat_id, text):
    data = json.dumps({"chat_id": str(chat_id), "text": text}).encode("utf-8")
    req = urllib.request.Request(
        API + "/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def get_offset():
    if OFFSET_FILE.exists():
        txt = OFFSET_FILE.read_text(encoding="utf-8").strip()
        if txt.isdigit():
            return int(txt)
    return None

def set_offset(v):
    OFFSET_FILE.write_text(str(v), encoding="utf-8")

def handle_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if not chat_id:
        return

    if not text.strip():
        tg_send_message(chat_id, "暂时只处理文本消息。")
        return

    log(f"receive chat_id={chat_id} text={text[:200]!r}")

    try:
        proc = subprocess.run(
            [RUNNER, str(chat_id), text],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=600,
            env={**os.environ, "HERMES_HOME": HERMES_HOME},
        )
        log(f"runner exit={proc.returncode} output={proc.stdout[:2000]!r}")
        if proc.returncode != 0:
            tg_send_message(chat_id, f"处理失败：\n{proc.stdout[-3000:]}")
    except subprocess.TimeoutExpired:
        log("runner timeout")
        tg_send_message(chat_id, "任务执行超时，但服务仍在运行，请稍后重试。")
    except Exception as e:
        log(f"runner exception: {e!r}")
        tg_send_message(chat_id, f"处理异常：{e!r}")

def main():
    log("telegram bridge started")
    offset = get_offset()
    while True:
        try:
            data = tg_get_updates(offset=offset, timeout=25)
            if not data.get("ok"):
                log(f"bad getUpdates response: {data!r}")
                time.sleep(3)
                continue

            for item in data.get("result", []):
                update_id = item["update_id"]
                offset = update_id + 1
                set_offset(offset)

                msg = item.get("message") or item.get("edited_message")
                if not msg:
                    continue

                handle_message(msg)

        except Exception as e:
            log(f"main loop exception: {e!r}")
            time.sleep(5)

if __name__ == "__main__":
    main()
