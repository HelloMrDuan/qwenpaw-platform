import AiBot, { generateReqId } from '@wecom/aibot-node-sdk';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const BASE = '/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes';
const HERMES_HOME = `${BASE}/data`;
const ENV_FILE = `${HERMES_HOME}/.env`;
const HERMES_BIN = `${BASE}/hermes.sh`;
const RUNNER = `${HERMES_HOME}/skills/openclaw-imports/sn-image-base/scripts/sn_agent_runner.py`;
const OUT_DIR = `${HERMES_HOME}/output`;
const LOG_FILE = `${BASE}/wecom_bridge.log`;

fs.mkdirSync(OUT_DIR, { recursive: true });

function loadEnv(file) {
  const out = {};
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const i = line.indexOf('=');
    const k = line.slice(0, i).trim();
    let v = line.slice(i + 1).trim();
    if (v.length >= 2 && ((v[0] === '"' && v.at(-1) === '"') || (v[0] === "'" && v.at(-1) === "'"))) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

const E = loadEnv(ENV_FILE);
const BOT_ID = E.WECOM_BOT_ID;
const BOT_SECRET = E.WECOM_BOT_SECRET;
const SN_API_KEY = E.SN_API_KEY || E.SENSENOVA_API_KEY;
const SN_BASE_URL = (E.SN_BASE_URL || 'https://token.sensenova.cn/v1').replace(/\/+$/, '');
const SN_CHAT_MODEL = E.SN_CHAT_MODEL || 'sensenova-6.8-flash-lite';

if (!BOT_ID || !BOT_SECRET) throw new Error('WECOM credentials missing');
if (!SN_API_KEY) throw new Error('SenseNova API key missing');
if (!fs.existsSync(HERMES_BIN)) throw new Error(`Hermes not found: ${HERMES_BIN}`);
if (!fs.existsSync(RUNNER)) throw new Error(`SenseNova runner not found: ${RUNNER}`);

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function run(cmd, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, {
      env: { ...process.env, ...E, HERMES_HOME },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { p.kill('SIGTERM'); } catch {}
      reject(new Error(`timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    p.stdout.on('data', d => stdout += d.toString());
    p.stderr.on('data', d => stderr += d.toString());
    p.on('error', err => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });
    p.on('close', code => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    });
  });
}

function normalizeAspect(v) {
  const allowed = new Set(['1:1','16:9','9:16','3:2','2:3','4:3','3:4','2:1','1:2','3:1','1:3']);
  return allowed.has(v) ? v : '1:1';
}

async function routeRequest(text) {
  const system = `你是请求路由器。只输出一个 JSON 对象，不要 Markdown，不要解释。
字段：
route: image | agent
prompt: 后续执行使用的中文提示词
aspect_ratio: 1:1 | 16:9 | 9:16 | 3:2 | 2:3 | 4:3 | 3:4 | 2:1 | 1:2 | 3:1 | 1:3

规则：
- 用户明确要求生成、绘制、制作一张普通图片、插画、头像、海报、封面、场景图、产品图等：route=image。
- 问答、Shell、研究、记忆、Skills、定时任务、信息分析以及其他 Agent 任务：route=agent。
- 不使用关键词表机械匹配，按用户真实语义判断。
- prompt 必须保留用户原意，不擅自改变主题。
- 用户明确给出比例时必须保留；未给比例时根据内容合理选择。`;

  const res = await fetch(`${SN_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${SN_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: SN_CHAT_MODEL,
      temperature: 0,
      max_tokens: 180,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: text },
      ],
    }),
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) throw new Error(`router HTTP ${res.status}: ${(await res.text()).slice(0, 500)}`);
  const data = await res.json();
  const content = String(data?.choices?.[0]?.message?.content || '').trim();
  const m = content.match(/\{[\s\S]*\}/);
  if (!m) throw new Error(`router non-JSON: ${content.slice(0, 300)}`);

  const obj = JSON.parse(m[0]);
  if (!['image', 'agent'].includes(obj.route)) obj.route = 'agent';
  obj.prompt = String(obj.prompt || text);
  obj.aspect_ratio = normalizeAspect(String(obj.aspect_ratio || '1:1'));
  return obj;
}

function cleanText(s) {
  let t = String(s || '').trim();
  t = t.replace(/\/(?:run\/csi|tmp)\/[^\s"'`]+\.(?:png|jpg|jpeg|webp|pdf)/gi, '');
  t = t.replace(/\n{3,}/g, '\n\n').trim();
  if (!t) t = '处理完成。';
  return t;
}

function targetId(frame) {
  return frame?.body?.chattype === 'group'
    ? frame?.body?.chatid
    : frame?.body?.from?.userid;
}

const client = new AiBot.WSClient({
  botId: BOT_ID,
  secret: BOT_SECRET,
  maxReconnectAttempts: -1,
  heartbeatInterval: 30000,
  logger: {
    debug: () => {},
    info: (...a) => log(a.join(' ')),
    warn: (...a) => log(`WARN ${a.join(' ')}`),
    error: (...a) => log(`ERROR ${a.join(' ')}`),
  },
});

const seen = new Set();
function duplicate(id) {
  if (!id) return false;
  if (seen.has(id)) return true;
  seen.add(id);
  if (seen.size > 300) seen.delete(seen.values().next().value);
  return false;
}

client.on('connected', () => log('WECOM WS CONNECTED'));
client.on('authenticated', () => log('WECOM AUTH OK'));
client.on('reconnecting', n => log(`WECOM RECONNECTING ${n}`));
client.on('disconnected', reason => log(`WECOM DISCONNECTED ${reason}`));
client.on('error', err => log(`WECOM ERROR ${err?.stack || err}`));

client.on('event.enter_chat', async frame => {
  try {
    await client.replyWelcome(frame, {
      msgtype: 'text',
      text: { content: 'Hermes 已连接。可以直接聊天、执行任务或让我生成图片。' },
    });
  } catch (e) {
    log(`welcome error: ${e?.stack || e}`);
  }
});

let queue = Promise.resolve();

async function handleText(frame) {
  const msgid = frame?.body?.msgid;
  if (duplicate(msgid)) return;

  const text = String(frame?.body?.text?.content || '').trim();
  if (!text) return;

  const streamId = generateReqId('stream');
  log(`message ${msgid || '-'}: ${text.slice(0, 180)}`);

  try {
    await client.replyStream(frame, streamId, '正在处理…', false);
  } catch (e) {
    log(`initial reply error: ${e?.message || e}`);
  }

  let route;
  try {
    route = await routeRequest(text);
    log(`route=${route.route} aspect=${route.aspect_ratio}`);
  } catch (e) {
    log(`router failed -> agent: ${e?.message || e}`);
    route = { route: 'agent', prompt: text, aspect_ratio: '1:1' };
  }

  if (route.route === 'image') {
    try {
      await client.replyStream(frame, streamId, '正在生成图片…', false);

      const out = path.join(OUT_DIR, `wecom_${Date.now()}.png`);
      const r = await run('python3', [
        RUNNER, 'sn-image-generate',
        '--prompt', route.prompt,
        '--aspect-ratio', route.aspect_ratio,
        '--image-size', '2k',
        '--save-path', out,
        '--output-format', 'json',
      ], 300000);

      if (r.code !== 0 || !fs.existsSync(out)) {
        throw new Error(`image generation failed: ${(r.stderr || r.stdout).slice(-2500)}`);
      }

      await client.replyStream(frame, streamId, '图片已生成，正在发送…', true);

      const buf = fs.readFileSync(out);
      const up = await client.uploadMedia(buf, {
        type: 'image',
        filename: path.basename(out),
      });

      const target = targetId(frame);
      if (!target) throw new Error('cannot resolve WeCom target id');
      await client.sendMediaMessage(target, 'image', up.media_id);
      log(`image sent: ${out}`);
      return;
    } catch (e) {
      log(`image handler error: ${e?.stack || e}`);
      try {
        await client.replyStream(frame, streamId, `图片处理失败：${String(e?.message || e).slice(0, 1200)}`, true);
      } catch {}
      return;
    }
  }

  try {
    const r = await run(HERMES_BIN, ['-z', route.prompt], 600000);
    const answer = cleanText(r.stdout || r.stderr).slice(-18000);
    await client.replyStream(frame, streamId, answer, true);
    log(`agent done code=${r.code}`);
  } catch (e) {
    log(`agent handler error: ${e?.stack || e}`);
    try {
      await client.replyStream(frame, streamId, `处理失败：${String(e?.message || e).slice(0, 1500)}`, true);
    } catch {}
  }
}

client.on('message.text', frame => {
  queue = queue.then(() => handleText(frame)).catch(e => log(`queue error: ${e?.stack || e}`));
});

process.on('SIGINT', () => {
  try { client.disconnect(); } catch {}
  process.exit(0);
});
process.on('SIGTERM', () => {
  try { client.disconnect(); } catch {}
  process.exit(0);
});
process.on('uncaughtException', e => log(`uncaughtException: ${e?.stack || e}`));
process.on('unhandledRejection', e => log(`unhandledRejection: ${e?.stack || e}`));

client.connect();
log('WECOM BRIDGE STARTING');
