#!/usr/bin/env python3
"""
微信客服 Gateway V3.4
- 监听 127.0.0.1:8793
- 使用 wecom-public Agent 处理 AI 对话（支持 text/image JSON 返回）
- SQLite 去重与对话历史（兼容迁移 gateway-v32.db）
- PRAGMA table_info + ALTER TABLE 兼容迁移
- WAL / busy_timeout
- generated_images 目录
- ACK 先发送
- QwenPaw SESSION 行剥离
- U1 Fast / sensenova-u1-fast / sn_agent_runner.py
- prepare_wecom_image / upload_image_media / send_image_message
- 图片大小限制 <=1990000 bytes
- /cgi-bin/media/upload
- msgtype=image
- processing/completed/failed
- 安全日志脱敏
"""
import os, sys, json, re, time, hmac, hashlib, base64, struct, sqlite3, threading, subprocess, ssl, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from Crypto.Cipher import AES
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# ======================== 配置加载 ========================
BASE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    cfg = {}
    env_path = os.path.join(BASE, '.env')
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                cfg[k] = v
    return cfg

CFG = load_env()
TOKEN = CFG.get('TOKEN', '')
AESKEY = CFG.get('AESKEY', '')
CORP_ID = CFG.get('CORP_ID', '')
APP_SECRET = CFG.get('APP_SECRET', '')
OPEN_KFID = CFG.get('OPEN_KFID', '')

# AES 密钥处理
AES_KEY = base64.b64decode(AESKEY + '=')

# ======================== 日志 ========================
LOG_PATH = os.path.join(BASE, 'gateway-v34.log')
DB_PATH = os.path.join(BASE, 'gateway-v32.db')
GENERATED_DIR = os.path.join(BASE, 'generated')
U1_RUNNER = "/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes/data/skills/openclaw-imports/sn-image-base/scripts/sn_agent_runner.py"

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def safe_log(external_userid, msgid, msg):
    """安全日志脱敏"""
    eid = external_userid[:8] + '...' if external_userid and len(external_userid) > 8 else (external_userid or '')
    mid = msgid[:12] + '...' if msgid and len(msgid) > 12 else (msgid or '')
    log(f"[{eid}|{mid}] {msg}")

def sanitize_log_text(text):
    """脱敏日志中的敏感信息"""
    if not text:
        return text
    patterns = [
        (r'(api_key|apikey|api-key)\s*[=:]\s*\S+', r'\1=***'),
        (r'(token|secret)\s*[=:]\s*\S+', r'\1=***'),
        (r'Authorization\s*:\s*Bearer\s+\S+', 'Authorization: Bearer ***'),
        (r'Bearer\s+\S+', 'Bearer ***'),
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result

# ======================== 加密解密 ========================
def signature(timestamp, nonce, encrypt):
    lst = [TOKEN, str(timestamp), str(nonce), encrypt]
    lst.sort()
    s = ''.join(lst)
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def decrypt(encrypted):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_KEY[:16])
    encrypted_bytes = base64.b64decode(encrypted)
    decrypted = cipher.decrypt(encrypted_bytes)
    pad = decrypted[-1]
    if pad < 1 or pad > 32:
        raise ValueError('bad padding')
    decrypted = decrypted[:-pad]
    msg_len = struct.unpack('!I', decrypted[16:20])[0]
    return decrypted[20:20 + msg_len].decode('utf-8')

def encrypt_text(plaintext):
    """加密文本，用于 echostr 验证等"""
    msg = plaintext.encode('utf-8')
    msg_len = struct.pack('!I', len(msg))
    import random
    random_bytes = bytes([random.randint(0, 255) for _ in range(16)])
    padded = random_bytes + msg_len + msg
    block_size = 32
    pad_len = block_size - (len(padded) % block_size)
    padded += bytes([pad_len] * pad_len)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_KEY[:16])
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode('utf-8')

def get_encrypt_from_xml(body):
    root = ET.fromstring(body)
    encrypt = root.find('Encrypt')
    if encrypt is None or not encrypt.text:
        raise ValueError('missing Encrypt')
    return encrypt.text

# ======================== SQLite ========================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 兼容迁移：检查 processed_messages 表结构
    c.execute("PRAGMA table_info(processed_messages)")
    columns = [row['name'] for row in c.fetchall()]
    for col, coltype in [
        ('status', 'TEXT NOT NULL DEFAULT "completed"'),
        ('external_userid', 'TEXT'),
        ('open_kfid', 'TEXT'),
        ('msgtype', 'TEXT'),
        ('content_hash', 'TEXT'),
        ('updated_at', 'TEXT')
    ]:
        if col not in columns:
            try:
                c.execute(f'ALTER TABLE processed_messages ADD COLUMN {col} {coltype}')
                log(f" migrated processed_messages add column {col}")
            except Exception:
                pass
    
    # 已处理消息（带状态）
    c.execute('''
        CREATE TABLE IF NOT EXISTS processed_messages (
            msgid TEXT PRIMARY KEY,
            external_userid TEXT,
            open_kfid TEXT,
            msgtype TEXT,
            content_hash TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    # 对话历史
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_userid TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_external_userid 
        ON conversation_messages(external_userid, created_at)
    ''')
    # 图片生成记录
    c.execute('''
        CREATE TABLE IF NOT EXISTS generated_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msgid TEXT NOT NULL,
            external_userid TEXT,
            open_kfid TEXT,
            prompt TEXT,
            image_path TEXT,
            upload_image_path TEXT,
            media_id TEXT,
            upload_status TEXT,
            send_status TEXT,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_generated_images_msgid
        ON generated_images(msgid)
    ''')
    conn.commit()
    conn.close()

def get_message_status(msgid):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('SELECT status FROM processed_messages WHERE msgid = ?', (msgid,))
        row = c.fetchone()
        return row['status'] if row else None
    finally:
        conn.close()

def mark_message_processing(msgid, external_userid):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'INSERT OR IGNORE INTO processed_messages (msgid, external_userid, status, created_at) VALUES (?, ?, ?, ?)',
            (msgid, external_userid, 'processing', datetime.now(timezone.utc).isoformat())
        )
        claimed = (c.rowcount == 1)
        conn.commit()
        return claimed
    finally:
        conn.close()

def update_message_status(msgid, status):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'UPDATE processed_messages SET status = ? WHERE msgid = ?',
            (status, msgid)
        )
        conn.commit()
    finally:
        conn.close()

def add_conversation_message(external_userid, role, content):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'INSERT INTO conversation_messages (external_userid, role, content, created_at) VALUES (?, ?, ?, ?)',
            (external_userid, role, content, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def insert_generated_image(msgid, external_userid, open_kfid, prompt):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'INSERT INTO generated_images (msgid, external_userid, open_kfid, prompt, upload_status, send_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (msgid, external_userid, open_kfid, prompt, 'pending', 'pending', datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def update_generated_image(msgid, **kwargs):
    conn = get_db()
    try:
        c = conn.cursor()
        sets = []
        vals = []
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(msgid)
        c.execute(f"UPDATE generated_images SET {', '.join(sets)} WHERE msgid = ?", vals)
        conn.commit()
    finally:
        conn.close()

SYNC_CURSOR_PATH = os.path.join(BASE, 'sync_cursor_v345.json')

def load_cursor():
    if os.path.exists(SYNC_CURSOR_PATH):
        try:
            with open(SYNC_CURSOR_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('cursor', '')
        except Exception:
            pass
    return ''

def save_cursor(cursor):
    try:
        tmp_path = SYNC_CURSOR_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump({'cursor': cursor}, f)
        os.replace(tmp_path, SYNC_CURSOR_PATH)
    except Exception as e:
        safe_log('', '', f"save_cursor error: {e}")

def poll_loop():
    """定时轮询 sync_msg 作为 callback 兜底"""
    while True:
        try:
            safe_log('', '', "poll start")
            cursor = load_cursor()
            
            all_messages = []
            has_more = True
            next_cursor = cursor
            new_count = 0
            dup_count = 0
            
            while has_more:
                result = sync_msg('', next_cursor)
                if not result or result.get('errcode') != 0:
                    safe_log('', '', f"poll error errcode={result.get('errcode') if result else 'None'}")
                    break
                
                msg_list = result.get('msg_list', [])
                for msg in msg_list:
                    msgid = msg.get('msgid', '')
                    msgtype = msg.get('msgtype', '')
                    origin = msg.get('origin', 0)
                    external_userid = msg.get('external_userid', '')
                    msg_open_kfid = msg.get('open_kfid', '')
                    content = ''
                    
                    if msgtype == 'text':
                        content = msg.get('text', {}).get('content', '')
                    else:
                        continue
                    
                    if not msgid or not external_userid or msg_open_kfid != OPEN_KFID or origin != 3 or not content.strip():
                        continue
                    
                    status = get_message_status(msgid)
                    if status == 'completed':
                        dup_count += 1
                        continue
                    
                    if status == 'processing':
                        dup_count += 1
                        continue
                    
                    if status == 'failed':
                        dup_count += 1
                        continue
                    
                    new_count += 1
                    threading.Thread(
                        target=process_kf_message,
                        args=(msgid, external_userid, content.strip()),
                        daemon=True
                    ).start()
                
                has_more = result.get('has_more', False)
                next_cursor = result.get('next_cursor', '')
            
            if next_cursor:
                save_cursor(next_cursor)
            
            safe_log('', '', f"poll count={len(msg_list) if 'msg_list' in dir() else 0} new={new_count} duplicate={dup_count} next_cursor_present={'true' if next_cursor else 'false'}")
        except Exception as e:
            safe_log('', '', f"poll error: {e}")
        
        time.sleep(30)

def get_recent_messages(external_userid, limit=12):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'SELECT role, content FROM conversation_messages WHERE external_userid = ? ORDER BY created_at DESC LIMIT ?',
            (external_userid, limit)
        )
        rows = c.fetchall()
        return list(reversed([dict(row) for row in rows]))
    finally:
        conn.close()

# ======================== Access Token ========================
_token_cache = {'token': None, 'expires_at': 0}

def get_access_token():
    now = time.time()
    if _token_cache['token'] and now < _token_cache['expires_at']:
        return _token_cache['token']
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={APP_SECRET}"
    req = urllib.request.Request(url)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log(f"get_access_token request error: {e}")
        return None
    
    if data.get('errcode') != 0:
        log(f"get_access_token error: {data}")
        return None
    
    token = data.get('access_token', '')
    expires_in = data.get('expires_in', 7200)
    _token_cache['token'] = token
    _token_cache['expires_at'] = now + expires_in - 300
    log("access_token refreshed")
    return token

# ======================== 微信 API ========================
def wechat_api_call(path, payload):
    token = get_access_token()
    if not token:
        return None
    url = f"https://qyapi.weixin.qq.com{path}?access_token={token}"
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log(f"wechat_api_call {path} error: {e}")
        return None

def sync_msg(external_userid, cursor=''):
    """拉取消息"""
    payload = {
        "open_kfid": OPEN_KFID,
        "external_userid": external_userid,
        "cursor": cursor,
        "token": "",
        "limit": 100
    }
    result = wechat_api_call('/cgi-bin/kf/sync_msg', payload)
    return result

def send_text_message(external_userid, content):
    """发送文本消息"""
    payload = {
        "touser": external_userid,
        "open_kfid": OPEN_KFID,
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    result = wechat_api_call('/cgi-bin/kf/send_msg', payload)
    return result

def send_image_message(external_userid, media_id):
    """发送图片消息"""
    payload = {
        "touser": external_userid,
        "open_kfid": OPEN_KFID,
        "msgtype": "image",
        "image": {
            "media_id": media_id
        }
    }
    result = wechat_api_call('/cgi-bin/kf/send_msg', payload)
    return result

def get_service_state(external_userid):
    """获取用户会话状态"""
    payload = {
        "open_kfid": OPEN_KFID,
        "external_userid": external_userid
    }
    result = wechat_api_call('/cgi-bin/kf/service_state/get', payload)
    if result:
        errcode = result.get('errcode', -1)
        errmsg = result.get('errmsg', '')
        safe_log(external_userid, '', f"service_state errcode={errcode} errmsg={errmsg}")
        if errcode == 0:
            return result.get('service_state', -1)
    return -1

# ======================== 图片处理 ========================
def prepare_wecom_image(image_path):
    """准备图片用于微信发送，确保大小 <= 1990000 bytes"""
    if not os.path.exists(image_path):
        raise RuntimeError("WECHAT_IMAGE_TOO_LARGE")
    
    file_size = os.path.getsize(image_path)
    ext = os.path.splitext(image_path)[1].lower()
    
    # 如果已经足够小且是 JPG/PNG，直接返回
    if file_size <= 1990000 and ext in ('.jpg', '.jpeg', '.png'):
        return image_path
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    base_name = os.path.basename(image_path)
    name, _ = os.path.splitext(base_name)
    output_path = os.path.join(GENERATED_DIR, f"wecom_{name}.jpg")
    
    try:
        from PIL import Image
        img = Image.open(image_path)
        
        # RGBA / P 转 RGB
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 质量循环
        qualities = [92, 88, 82, 76, 70]
        max_sizes = [2048, 1800, 1600, 1400, 1200]
        
        for quality in qualities:
            for max_size in max_sizes:
                w, h = img.size
                if max(w, h) > max_size:
                    ratio = max_size / max(w, h)
                    new_w = int(w * ratio)
                    new_h = int(h * ratio)
                    test_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                else:
                    test_img = img
                
                test_img.save(output_path, 'JPEG', quality=quality)
                size = os.path.getsize(output_path)
                
                if size <= 1990000:
                    safe_log('', '', f"image prepared {file_size} -> {size} quality={quality} size={max_size}")
                    return output_path
        
        # 全部失败
        raise RuntimeError("WECHAT_IMAGE_TOO_LARGE")
    except RuntimeError:
        raise
    except Exception as e:
        safe_log('', '', f"image prepare error: {e}")
        raise RuntimeError("WECHAT_IMAGE_TOO_LARGE")

def upload_image_media(image_path):
    """上传图片到微信媒体库"""
    token = get_access_token()
    if not token:
        return None
    
    prepared = prepare_wecom_image(image_path)
    if not prepared:
        return None
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"
    
    try:
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        with open(prepared, 'rb') as f:
            file_data = f.read()
        
        ext = os.path.splitext(prepared)[1].lower()
        if ext in ('.jpg', '.jpeg'):
            content_type = 'image/jpeg'
        elif ext == '.png':
            content_type = 'image/png'
        else:
            content_type = 'application/octet-stream'
        
        body = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="media"; filename="{os.path.basename(prepared)}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode('utf-8') + file_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
        
        req = urllib.request.Request(url, data=body, headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}'
        })
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('errcode') == 0:
                return result.get('media_id')
            else:
                safe_log('', '', f"upload error: {result}")
                return None
    except Exception as e:
        safe_log('', '', f"upload exception: {e}")
        return None

# ======================== QwenPaw 调用 ========================
QWENPAW_BIN = '/app/venv/bin/qwenpaw'
if not os.path.exists(QWENPAW_BIN):
    QWENPAW_BIN = os.popen('which qwenpaw').read().strip() or 'qwenpaw'

def build_prompt(external_userid, user_message):
    """构建发送给 wecom-public agent 的 prompt"""
    history = get_recent_messages(external_userid, limit=12)
    prompt = """你正在处理一个微信客服用户的对话。

【安全约束】
你是公共微信AI助手。
不得访问、泄露或描述私人用户数据、服务器凭据、SSH信息、Token、Secret、私人Memory。
不得执行服务器管理、Shell、SSH、Tailscale管理等高权限操作。
如果用户要求这些能力，明确说明公共助手没有权限。

【系统已经具备图片生成后端】
当用户要求生成图片时，你不需要亲自生成图片。
Gateway 会自动调用 SenseNova U1 Fast 生成图片。
你只需要把图片需求转换成完整的图片生成提示词，返回 {"mode":"image","prompt":"..."}。

【强制输出协议】
只能输出以下两种 JSON 之一，不要输出其他内容：

text 模式：{"mode":"text","reply":"最终文字回答"}
image 模式：{"mode":"image","prompt":"完整图片生成提示词"}

判断规则：
- 普通文字问题、知识问答、聊天 → text 模式
- 生成、绘制、制作、创建图片或视觉内容 → image 模式

不要声称没有图片生成能力。
不要推荐第三方图片工具。
不要输出 Markdown 大标题。
微信回复尽量简洁自然。

"""
    if history:
        prompt += "【历史对话】\n"
        for msg in history:
            role = "用户" if msg['role'] == 'user' else "助手"
            prompt += f"{role}：{msg['content']}\n"
        prompt += "\n"
    
    prompt += f"【当前用户消息】\n{user_message}\n\n只输出 JSON，不要额外解释。"
    return prompt

def strip_session_lines(text):
    """剥离 QwenPaw SESSION 行"""
    if not text:
        return text
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if 'SESSION:' in line or line.strip().startswith('[') and 'SESSION' in line:
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()

def load_sensenova_env():
    """安全加载 SenseNova 环境变量"""
    env_path = "/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes/data/.env"
    env = {}
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k] = v
    return env

def generate_u1_image(prompt, msgid):
    """调用 sn_agent_runner.py 生成图片，最多重试2次"""
    if not os.path.exists(U1_RUNNER):
        safe_log('', msgid, f"u1 runner not found: {U1_RUNNER}")
        return None
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    image_path = os.path.join(GENERATED_DIR, f"u1_{msgid}.png")
    
    env = os.environ.copy()
    sensenova_env = load_sensenova_env()
    env.update(sensenova_env)
    env['PATH'] = '/usr/bin:/bin:' + env.get('PATH', '')
    
    last_error = None
    for attempt in range(1, 3):
        try:
            proc = subprocess.run(
                [
                    sys.executable, U1_RUNNER,
                    'sn-image-generate',
                    '--prompt', prompt,
                    '--image-size', '2k',
                    '--aspect-ratio', '1:1',
                    '--save-path', image_path
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=BASE
            )
            
            stdout_text = sanitize_log_text(proc.stdout or '')
            stderr_text = sanitize_log_text(proc.stderr or '')
            
            if proc.returncode != 0:
                safe_log('', msgid, f"u1 attempt={attempt} failed returncode={proc.returncode}")
                safe_log('', msgid, f"u1 attempt={attempt} stdout={stdout_text[-800:]}")
                safe_log('', msgid, f"u1 attempt={attempt} stderr={stderr_text[-1500:]}")
                last_error = proc.returncode
                if attempt == 1:
                    time.sleep(5)
                continue
            
            if not os.path.exists(image_path):
                safe_log('', msgid, f"u1 attempt={attempt} failed: output not found")
                last_error = "output not found"
                if attempt == 1:
                    time.sleep(5)
                continue
            
            file_size = os.path.getsize(image_path)
            if file_size <= 0:
                safe_log('', msgid, f"u1 attempt={attempt} failed: empty file")
                last_error = "empty file"
                if attempt == 1:
                    time.sleep(5)
                continue
            
            # Pillow 验证
            try:
                from PIL import Image
                img = Image.open(image_path)
                img.verify()
            except Exception as e:
                safe_log('', msgid, f"u1 attempt={attempt} failed: invalid image: {e}")
                last_error = str(e)
                if attempt == 1:
                    time.sleep(5)
                continue
            
            safe_log('', msgid, f"u1 generated attempt={attempt} size={file_size}")
            return image_path
        except subprocess.TimeoutExpired:
            safe_log('', msgid, f"u1 attempt={attempt} timeout")
            last_error = "timeout"
            if attempt == 1:
                time.sleep(5)
            continue
        except Exception as e:
            safe_log('', msgid, f"u1 attempt={attempt} error: {e}")
            last_error = str(e)
            if attempt == 1:
                time.sleep(5)
            continue
    
    safe_log('', msgid, f"u1 generate failed after 2 attempts last_error={last_error}")
    return None

def call_agent(prompt):
    """调用 wecom-public agent（兼容旧逻辑）"""
    try:
        env = os.environ.copy()
        env['PATH'] = '/usr/bin:/bin:' + env.get('PATH', '')
        
        proc = subprocess.run(
            [
                QWENPAW_BIN,
                'agents', 'chat',
                '--from-agent', 'wecom-public',
                '--to-agent', 'wecom-public',
                '--text', prompt
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        
        stdout = proc.stdout or ''
        stderr = proc.stderr or ''
        
        # 剥离 SESSION 行
        response = strip_session_lines(stdout).strip()
        
        if proc.returncode != 0 or not response:
            safe_log('', '', f"agent failed: returncode={proc.returncode}, stderr={stderr[:200]}")
            return None
        
        return response
    except subprocess.TimeoutExpired:
        safe_log('', '', "agent timeout after 120s")
        return None
    except Exception as e:
        safe_log('', '', f"agent error: {e}")
        return None

# ======================== 消息处理 ========================
def send_ack(external_userid):
    """发送处理中 ack"""
    try:
        result = send_text_message(external_userid, "🤖 已收到，正在处理，请稍等…")
        if result:
            errcode = result.get('errcode', -1)
            errmsg = result.get('errmsg', '')
            safe_log(external_userid, '', f"ack send errcode={errcode} errmsg={errmsg}")
        else:
            safe_log(external_userid, '', "ack send failed: no response")
    except Exception as e:
        safe_log(external_userid, '', f"ack send error: {e}")

def process_kf_message(msgid, external_userid, content):
    """处理单条客服消息"""
    request_started = time.time()
    
    status = get_message_status(msgid)
    if status == 'completed':
        safe_log(external_userid, msgid, "duplicate skip")
        return
    if status == 'processing':
        safe_log(external_userid, msgid, "processing skip")
        return
    if status == 'failed':
        safe_log(external_userid, msgid, "failed skip")
        return
    
    claimed = mark_message_processing(msgid, external_userid)
    if not claimed:
        safe_log(external_userid, msgid, "atomic claim lost duplicate skip")
        return
    
    claim_done = time.time()
    
    state = get_service_state(external_userid)
    safe_log(external_userid, msgid, f"service_state={state}")
    
    # ACK 先发送
    safe_log(external_userid, msgid, "ack start")
    if state in (0, 1):
        send_ack(external_userid)
    else:
        safe_log(external_userid, msgid, f"ack skip state={state}")
    ack_done = time.time()
    
    add_conversation_message(external_userid, 'user', content)
    
    prompt = build_prompt(external_userid, content)
    safe_log(external_userid, msgid, "agent start")
    agent_started = time.time()
    
    # 调用 wecom-public，要求返回严格 JSON
    agent_reply = call_agent(prompt)
    
    agent_done = time.time()
    duration = agent_done - agent_started
    
    if agent_reply is None:
        agent_reply = "🤖 抱歉，刚才处理失败了，请稍后再试。"
        safe_log(external_userid, msgid, f"agent error duration={duration:.2f}s")
        update_message_status(msgid, 'failed')
        add_conversation_message(external_userid, 'assistant', agent_reply)
        return
    
    # Agent 成功，仍保持 processing，不提前标 completed
    safe_log(external_userid, msgid, f"agent success duration={duration:.2f}s reply_len={len(agent_reply)}")
    add_conversation_message(external_userid, 'assistant', agent_reply)
    
    state = get_service_state(external_userid)
    safe_log(external_userid, msgid, f"service_state={state}")
    
    if state not in (0, 1):
        safe_log(external_userid, msgid, f"final send skip state={state}")
        update_message_status(msgid, 'failed')
        return
    
    # 严格解析 JSON 响应
    sent = False
    result = None
    
    try:
        # 去 SESSION 行
        cleaned = strip_session_lines(agent_reply)
        # 去 ```json / ```
        cleaned = re.sub(r'```json\s*', '', cleaned)
        cleaned = re.sub(r'```\s*', '', cleaned)
        cleaned = cleaned.strip()
        
        response_data = json.loads(cleaned)
        if isinstance(response_data, dict):
            mode = response_data.get('mode', '')
            
            if mode == 'text':
                reply = response_data.get('reply', '')
                if reply:
                    send_started = time.time()
                    result = send_text_message(external_userid, reply)
                    send_done = time.time()
                    sent = True
            elif mode == 'image':
                prompt_img = response_data.get('prompt', '')
                if prompt_img:
                    # 记录图片任务
                    insert_generated_image(msgid, external_userid, OPEN_KFID, prompt_img)
                    
                    # 生成图片
                    safe_log(external_userid, msgid, "generating image start")
                    u1_started = time.time()
                    image_path = generate_u1_image(prompt_img, msgid)
                    u1_done = time.time()
                    if image_path:
                        update_generated_image(msgid, image_path=image_path)
                        
                        # 准备上传
                        prepare_started = time.time()
                        prepared = prepare_wecom_image(image_path)
                        prepare_done = time.time()
                        if prepared:
                            update_generated_image(msgid, upload_image_path=prepared)
                            
                            # 上传
                            upload_started = time.time()
                            media_id = upload_image_media(prepared)
                            upload_done = time.time()
                            if media_id:
                                update_generated_image(msgid, media_id=media_id, upload_status='completed')
                                
                                # 发送图片
                                send_started = time.time()
                                result = send_image_message(external_userid, media_id)
                                send_done = time.time()
                                if result and result.get('errcode') == 0:
                                    update_generated_image(msgid, send_status='completed')
                                    sent = True
                                    safe_log(external_userid, msgid, "image send success")
                                    safe_log(external_userid, msgid, (
                                        f"PERF image "
                                        f"claim={claim_done-request_started:.2f}s "
                                        f"ack={ack_done-claim_done:.2f}s "
                                        f"agent={agent_done-agent_started:.2f}s "
                                        f"u1={u1_done-u1_started:.2f}s "
                                        f"prepare={prepare_done-prepare_started:.2f}s "
                                        f"upload={upload_done-upload_started:.2f}s "
                                        f"send={send_done-send_started:.2f}s "
                                        f"total={send_done-request_started:.2f}s"
                                    ))
                                else:
                                    update_generated_image(msgid, send_status='failed')
                                    safe_log(external_userid, msgid, f"image send error errcode={result.get('errcode') if result else 'None'}")
                            else:
                                update_generated_image(msgid, upload_status='failed')
                                safe_log(external_userid, msgid, "upload image failed")
                        else:
                            update_generated_image(msgid, upload_status='failed', send_status='failed')
                            safe_log(external_userid, msgid, "prepare image failed")
                    else:
                        update_generated_image(msgid, upload_status='failed', send_status='failed')
                        update_message_status(msgid, 'failed')
                        send_text_message(external_userid, "抱歉，图片生成暂时失败了，请稍后再试。")
                        safe_log(external_userid, msgid, "image generate failed fallback")
                        return
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        safe_log(external_userid, msgid, f"json parse error: {e}")
    
    if not sent:
        # 安全回退普通文本
        send_started = time.time()
        result = send_text_message(external_userid, agent_reply)
        send_done = time.time()
    
    if result:
        errcode = result.get('errcode', -1)
        errmsg = result.get('errmsg', '')
        if errcode == 0:
            safe_log(external_userid, msgid, "final send success")
            safe_log(external_userid, msgid, (
                f"PERF text "
                f"agent={agent_done-agent_started:.2f}s "
                f"send={send_done-send_started:.2f}s "
                f"total={send_done-request_started:.2f}s"
            ))
            update_message_status(msgid, 'completed')
        else:
            safe_log(external_userid, msgid, f"final send error errcode={errcode} errmsg={errmsg}")
            update_message_status(msgid, 'failed')
    else:
        safe_log(external_userid, msgid, "final send failed no response")
        update_message_status(msgid, 'failed')

def process_event_background(xml_content):
    """后台线程处理事件"""
    try:
        root = ET.fromstring(xml_content)
        event = root.findtext('Event', '')
        open_kfid = root.findtext('OpenKfId', '')
        
        safe_log('', '', f"callback event={event} open_kfid={open_kfid}")
        
        if event != 'kf_msg_or_event':
            return
        
        if open_kfid != OPEN_KFID:
            safe_log('', '', f"skip open_kfid mismatch: {open_kfid}")
            return
        
        # 从回调事件中取得用于同步消息的 Token
        token = root.findtext('Token', '')
        cursor = root.findtext('Cursor', '')
        safe_log('', '', f"sync start token_present={'true' if token else 'false'}")
        
        # 立即调用 sync_msg，不要求 external_userid 存在
        all_messages = []
        has_more = True
        next_cursor = cursor
        
        while has_more:
            result = sync_msg('', next_cursor)
            if not result or result.get('errcode') != 0:
                safe_log('', '', f"sync result errcode={result.get('errcode') if result else 'None'}")
                break
            
            msg_list = result.get('msg_list', [])
            all_messages.extend(msg_list)
            has_more = result.get('has_more', False)
            next_cursor = result.get('next_cursor', '')
        
        safe_log('', '', f"sync count={len(all_messages)}")
        
        # 遍历 msg_list，对每条 msg 再判断字段
        for msg in all_messages:
            msgid = msg.get('msgid', '')
            msgtype = msg.get('msgtype', '')
            origin = msg.get('origin', 0)
            external_userid = msg.get('external_userid', '')
            msg_open_kfid = msg.get('open_kfid', '')
            content = ''
            
            if msgtype == 'text':
                content = msg.get('text', {}).get('content', '')
            else:
                continue
            
            # 安全日志（脱敏）
            safe_log(external_userid, msgid, f"msg origin={origin} msgtype={msgtype} open_kfid_match={'true' if msg_open_kfid == OPEN_KFID else 'false'}")
            
            # 过滤条件
            if not msgid:
                continue
            if not external_userid:
                continue
            if msg_open_kfid != OPEN_KFID:
                continue
            if origin != 3:
                continue
            if not content or not content.strip():
                continue
            
            # 在后台线程处理
            threading.Thread(
                target=process_kf_message,
                args=(msgid, external_userid, content.strip()),
                daemon=True
            ).start()
    
    except Exception as e:
        safe_log('', '', f"process_event_background error: {e}")

# ======================== HTTP 服务 ========================
class Handler(BaseHTTPRequestHandler):
    def out(self, code, body):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, *args):
        pass
    
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == '/healthz':
            return self.out(200, 'OK')
        
        if parsed.path != '/wecom/kf/callback':
            return self.out(404, 'Not Found')
        
        qs = urllib.parse.parse_qs(parsed.query)
        g = lambda k: qs.get(k, [''])[0]
        
        msg_signature = g('msg_signature')
        timestamp = g('timestamp')
        nonce = g('nonce')
        echostr = g('echostr')
        
        if not echostr:
            return self.out(400, 'Missing echostr')
        
        try:
            if signature(timestamp, nonce, echostr) != msg_signature:
                safe_log('', '', "GET verify bad signature")
                return self.out(403, 'Bad Signature')
            
            plain = decrypt(echostr)
            safe_log('', '', "GET verify OK")
            return self.out(200, plain)
        except Exception as e:
            safe_log('', '', f"GET error: {e}")
            return self.out(500, 'Error')
    
    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != '/wecom/kf/callback':
            return self.out(404, 'Not Found')
        
        qs = urllib.parse.parse_qs(parsed.query)
        g = lambda k: qs.get(k, [''])[0]
        
        content_length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(content_length)
        
        try:
            encrypt = get_encrypt_from_xml(body)
            if signature(g('timestamp'), g('nonce'), encrypt) != g('msg_signature'):
                safe_log('', '', "POST bad signature")
                return self.out(403, 'Bad Signature')
            
            xml = decrypt(encrypt)
            self.out(200, 'success')
            
            threading.Thread(target=process_event_background, args=(xml,), daemon=True).start()
        except Exception as e:
            safe_log('', '', f"POST error: {e}")
            return self.out(500, 'Error')

# ======================== 主程序 ========================
def main():
    port = 8798
    log(f"gateway start port={port} pid={os.getpid()}")
    
    # 确保 generated 目录存在
    os.makedirs(GENERATED_DIR, exist_ok=True)
    
    init_db()
    
    # 启动 polling fallback thread
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    log("poll fallback thread started")
    
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
