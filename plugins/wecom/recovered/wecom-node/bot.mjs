import AiBot from '@wecom/aibot-node-sdk';
import fs from 'fs';
import path from 'path';
import { createHash } from 'crypto';

const BASE = '/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes';
const HERMES_HOME = `${BASE}/data`;
const ENV_FILE = `${HERMES_HOME}/.env`;
const OUTPUT_DIR = `${HERMES_HOME}/output`;
const LOG_FILE = `${BASE}/wecom_bot.log`;

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

function loadEnv(file) {
  const env = {};
  for (const raw of fs.readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const i = line.indexOf('=');
    let value = line.slice(i + 1).trim();
    if (value.length >= 2 && ((value[0] === '"' && value.at(-1) === '"') || (value[0] === "'" && value.at(-1) === "'"))) value = value.slice(1, -1);
    env[line.slice(0, i).trim()] = value;
  }
  return env;
}

const E = loadEnv(ENV_FILE);
const BOT_ID = E.WECOM_BOT_ID;
const BOT_SECRET = E.WECOM_BOT_SECRET;

if (!BOT_ID || !BOT_SECRET) {
  throw new Error('WeCom credentials missing');
}

function log(message) {
  console.log(`[${new Date().toISOString()}] ${message}`);
}

const client = new AiBot.WSClient({
  botId: BOT_ID,
  secret: BOT_SECRET,
  maxReconnectAttempts: -1,
  heartbeatInterval: 300000,
  logger: {
    debug: (...a) => {},
    info: (...a) => log(a.join(' ')),
    warn: (...a) => log(a.join(' ')),
    error: (...a) => log(a.join(' ')),
  },
});

client.on('authenticated', () => log('WeCom AUTH OK'));
client.on('connected', () => log('WeCom WS CONNECTED'));
client.on('reconnecting', n => log(`WeCom RECONNECTING ${n}`));
client.on('disconnected', reason => log(`WeCom DISCONNECTED ${reason}`));
client.on('error', err => log(`WeCom ERROR ${err?.stack || err}`));

client.on('event.message', async (m) => {
  try {
    const text = m?.body?.content?.trim() || '';
    const chatType = m?.body?.chattype;
    const sender = m?.body?.from?.userid;
    log(`MSG chat=${chatType} from=${sender} text=${text.slice(0, 120)}`);
  } catch (e) {
    log(`handle message error: ${e?.message || e}`);
  }
});

client.on('event.enter_chat', async (m) => {
  try {
    const chatType = m?.body?.chattype;
    const sender = m?.body?.from?.userid;
    log(`ENTER chat=${chatType} from=${sender}`);
    await client.replyWechat(m, {
      msgtype: 'text',
      text: { content: 'Hermes 已就绪。\n发「帮助」看可用指令。\n暂不支持图片生成。' },
    }, true);
  } catch (e) {
    log(`enter chat reply error: ${e?.message || e}`);
  }
});

client.connect();
