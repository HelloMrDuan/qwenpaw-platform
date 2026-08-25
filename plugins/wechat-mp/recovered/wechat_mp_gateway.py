#!/usr/bin/env python3

import hashlib
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = "/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/wechat-mp"
QWENPAW = "/app/venv/bin/qwenpaw"

HOST = "127.0.0.1"
PORT = 8799
AGENT_TIMEOUT = 4

with open(BASE + "/token", encoding="utf-8") as f:
    TOKEN = f.read().strip()


def verify(signature, timestamp, nonce):
    if not all((signature, timestamp, nonce)):
        return False

    raw = "".join(
        sorted([TOKEN, timestamp, nonce])
    ).encode()

    return hashlib.sha1(raw).hexdigest() == signature


def value(root, name):
    n = root.find(name)
    return n.text.strip() if n is not None and n.text else ""


def reply_xml(to_user, from_user, text):
    root = ET.Element("xml")

    ET.SubElement(root, "ToUserName").text = to_user
    ET.SubElement(root, "FromUserName").text = from_user
    ET.SubElement(root, "CreateTime").text = str(int(time.time()))
    ET.SubElement(root, "MsgType").text = "text"
    ET.SubElement(root, "Content").text = text

    return ET.tostring(root, encoding="unicode")


def ask_agent(question):
    prompt = (
        "你正在通过微信公众号\u201c凌冬已至\u201d回答用户。"
        "只输出最终答案，不解释内部工具和执行过程。"
        "回答尽量简洁。"
        "涉及今天、最新、新闻、当前信息时，"
        "使用 public-web-research Skill 和 Tavily 实际联网查询。"
        "\n用户问题：" + question
    )

    try:
        p = subprocess.run(
            [
                QWENPAW,
                "agents", "chat",
                "--from-agent", "wecom-public",
                "--to-agent", "wecom-public",
                "--text", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=AGENT_TIMEOUT,
        )

        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()

        return "抱歉，本次处理失败，请稍后再试。"

    except subprocess.TimeoutExpired:
        return "这个问题处理时间较长，请稍后重新发送一次。"


class Handler(BaseHTTPRequestHandler):

    def send(self, code, body, content_type="text/plain; charset=utf-8"):
        raw = body.encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()

        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)

        if u.path == "/healthz":
            self.send(200, "ok")
            return

        if u.path != "/wechat/mp/callback":
            self.send(404, "not found")
            return

        q = urllib.parse.parse_qs(u.query)

        signature = q.get("signature", [""])[0]
        timestamp = q.get("timestamp", [""])[0]
        nonce = q.get("nonce", [""])[0]
        echostr = q.get("echostr", [""])[0]

        if verify(signature, timestamp, nonce):
            self.send(200, echostr)
        else:
            self.send(403, "invalid signature")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)

        if u.path != "/wechat/mp/callback":
            self.send(404, "not found")
            return

        q = urllib.parse.parse_qs(u.query)

        if not verify(
            q.get("signature", [""])[0],
            q.get("timestamp", [""])[0],
            q.get("nonce", [""])[0],
        ):
            self.send(403, "invalid signature")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            root = ET.fromstring(self.rfile.read(length))

            from_user = value(root, "FromUserName")
            to_user = value(root, "ToUserName")
            msg_type = value(root, "MsgType").lower()

            if msg_type == "event":
                self.send(200, "success")
                return

            if msg_type != "text":
                answer = "目前 AI 助手先支持文字消息。"
            else:
                content = value(root, "Content")
                answer = ask_agent(content) if content else "请输入问题。"

            xml = reply_xml(
                from_user,
                to_user,
                answer,
            )

            self.send(
                200,
                xml,
                "application/xml; charset=utf-8",
            )

        except Exception as e:
            print(
                "callback error:",
                type(e).__name__,
                str(e)[:500],
                flush=True,
            )

            self.send(200, "success")


if __name__ == "__main__":
    print(
        f"wechat-mp passive gateway start {HOST}:{PORT}",
        flush=True,
    )

    ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    ).serve_forever()
