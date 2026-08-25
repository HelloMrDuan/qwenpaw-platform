#!/usr/bin/env python3
import json, os, pathlib, re, subprocess, sys, time, urllib.request

BASE = "/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes"
HOME = f"{BASE}/data"
ENV_FILE = pathlib.Path(HOME) / ".env"
RUNNER = pathlib.Path(HOME) / "skills/openclaw-imports/sn-image-base/scripts/sn_agent_runner.py"
HERMES = f"{BASE}/hermes.sh"
OUT_DIR = pathlib.Path(HOME) / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_env(path):
    env = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] in ("'", '"'):
            v = v[1:-1]
        env[k.strip()] = v
    return env

E = load_env(ENV_FILE)
TOKEN = E.get("TELEGRAM_BOT_TOKEN", "")
SN_KEY = E.get("SN_CHAT_API_KEY") or E.get("SN_API_KEY") or E.get("SENSENOVA_API_KEY") or ""
SN_BASE = (E.get("SN_CHAT_BASE_URL") or E.get("SN_BASE_URL") or "https://token.sensenova.cn/v1").rstrip("/")
SN_MODEL = E.get("SN_CHAT_MODEL") or "sensenova-6.8-flash-lite"

if len(sys.argv) < 3:
    raise SystemExit("usage: fast_route.py <chat_id> <prompt>")
CHAT_ID = sys.argv[1]
USER_PROMPT = sys.argv[2]

def tg_text(text):
    if not text:
        return
    for i in range(0, len(text), 3800):
        body = json.dumps({"chat_id": CHAT_ID, "text": text[i:i+3800]}, ensure_ascii=False).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()

def tg_photo(path, caption=""):
    cmd = [
        "curl", "-fsS",
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
        "-F", f"chat_id={CHAT_ID}",
        "-F", f"photo=@{path}",
    ]
    if caption:
        cmd += ["-F", f"caption={caption}"]
    subprocess.run(cmd, check=True, timeout=60)

def route_request(text):
    system = """你是一个请求路由器。只输出一个JSON对象，不要Markdown，不要解释。
字段：
route: image | infographic | agent
prompt: 供后续执行的中文提示词
aspect_ratio: 1:1 | 16:9 | 9:16 | 3:2 | 2:3 | 4:3 | 3:4 | 2:1 | 1:2 | 3:1 | 1:3

规则：
- 普通文生图、插画、头像、海报、封面、场景图等：image。
- 明确要求高信息密度信息图、技术架构信息图、带大量文字结构与布局的信息图：infographic。
- 其他聊天、Shell、研究、记忆、Skills、定时任务等：agent。
- 不使用关键词表机械匹配，要按语义判断。
- prompt必须保留用户原意；image时只做必要的出图提示词整理，不擅自增加主题。
- 用户明确给出比例时必须保留；没给比例时按内容合理选择。
"""
    payload = {
        "model": SN_MODEL,
        "temperature": 0,
        "max_tokens": 220,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
    }
    req = urllib.request.Request(
        SN_BASE + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={
            "Authorization": f"Bearer {SN_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    content = data["choices"][0]["message"]["content"].strip()
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise ValueError("router returned non-JSON: " + content[:300])
    obj = json.loads(m.group(0))
    if obj.get("route") not in {"image", "infographic", "agent"}:
        obj["route"] = "agent"
    if obj.get("aspect_ratio") not in {"1:1","16:9","9:16","3:2","2:3","4:3 | 3:4 | 2:1 | 1:2 | 3:1 | 1:3"}:
        obj["aspect_ratio"] = "1:1"
    obj["prompt"] = str(obj.get("prompt") or text)
    return obj

def extract_media(text):
    matches = re.findall(r"(/[^\s\"']+\.(?:png|jpg|jpeg|webp))", text, flags=re.I)
    for p in reversed(matches):
        if os.path.isfile(p):
            return p
    return None

def clean_media_paths(text):
    return "\n".join(
        line for line in text.splitlines()
        if not re.search(r"/(?:run/csi|tmp)/[^\s]+\.(?:png|jpg|jpeg|webp)", line, re.I)
    ).strip()

try:
    r = route_request(USER_PROMPT)
except Exception:
    r = {"route": "agent", "prompt": USER_PROMPT, "aspect_ratio": "1:1"}

if r["route"] == "image":
    tg_text("正在生成图片…")
    out = OUT_DIR / f"tg^{time.strftime('%Y%m5d_%H%M%S')}.png"
    env = os.environ.copy()
    env.update(E)
    env["HERMES_HOME"] = HOME
    p = subprocess.run(
        [
            sys.executable, str(RUNNER), "sn-image-generate",
            "--prompt", r["prompt"],
            "--aspect-ratio", r["aspect_ratio"],
            "--image-size", "2k",
            "--save-path", str(out),
            "--output-format", "json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
        env=env,
    )
    if p.returncode == 0 and out.is_file():
        tg_photo(str(out), "生成完成")
    else:
        tg_text("图片生成失败：\n" + p.stdout[-3000:])
    raise SystemExit(0)

if r["route"] == "infographic":
    tg_text("正在生成信息图，这类任务会比普通图片慢一些…")
    p = subprocess.run(
        [HERMES, "chat", "-s", "sn-infographic", "-q", USER_PROMPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=900,
        env={**os.environ, **E, "HERMES_HOME": HOME},
    )
    media = extract_media(p.stdout)
    if media:
        tg_photo(media, "信息图生成完成")
    text = clean_media_paths(p.stdout)
    if text:
        tg_text(text[-3800:])
    raise SystemExit(0)

p = subprocess.run(
    [HERMES, "-z", USER_PROMPT],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    timeout=600,
    env={**os.environ, **E, "HERMES_HOME": HOME},
)
media = extract_media(p.stdout)
if media:
    tg_photo(media)
text = clean_media_paths(p.stdout)
if text:
    tg_text(text[-3800:])
