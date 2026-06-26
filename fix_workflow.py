#!/usr/bin/env python3
"""Apply all 5 CX fixes to Chat Bot.json while preserving existing node IDs."""
import json
import copy
import uuid

SRC = "/Users/sepehrjokanian/Documents/chatbotv5(error Must fixed)/Chat Bot.json"
OUT = "/Users/sepehrjokanian/Documents/chatbotv5(error Must fixed)/Chat Bot.json"

CHAT_ID = "={{\n$('Telegram Trigger').first().json.message?.chat?.id ??\n$('Telegram Trigger').first().json.callback_query?.message?.chat?.id\n}}"

SUPA_CRED = {"httpHeaderAuth": {"id": "0CmT4HAyc6wYbZx1", "name": "Supabase Service Role"}}
TG_CRED = {"telegramApi": {"id": "zhQHcOnlhrQxUCJ7", "name": "Telegram account"}}
GROQ_CRED = {"httpHeaderAuth": {"id": "apMxsjOLXISfOaf7", "name": "Header Auth account 2"}}


def uid():
    return str(uuid.uuid4())


def find_node(wf, name):
    for n in wf["nodes"]:
        if n["name"] == name:
            return n
    return None


def add_node(wf, node):
    wf["nodes"].append(node)
    return node


with open(SRC) as f:
    wf = json.load(f)

# ── 1. Normalize: robust shop_id / chat_id resolution ──────────────────────
find_node(wf, "Normalize")["parameters"]["jsCode"] = r"""function normalizePersian(text) {
  if (!text) return '';
  return text
    .replace(/\u064a/g, '\u06cc')
    .replace(/\u0643/g, '\u06a9')
    .replace(/[\u0660-\u0669]/g, d => '\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'.indexOf(d))
    .replace(/[\u06f0-\u06f9]/g, d => '\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9'.indexOf(d))
    .replace(/\u200c/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getShopId() {
  const nodes = [
    'Set Shop ID From Session',
    'Set Pending Shop ID',
    'Prepare Pending Query For RAG',
    'Prepare Category Search',
    'Save Chat Session',
    'Get Pending Query',
  ];
  for (const name of nodes) {
    try {
      const v = $(name).first()?.json?.shop_id;
      if (v) return v;
    } catch (e) {}
  }
  try {
    const v = $('Lookup Chat Session').first()?.json?.shop_id;
    if (v) return v;
  } catch (e) {}
  return null;
}

function getChatId() {
  return (
    $('Telegram Trigger').first().json.message?.chat?.id ??
    $('Telegram Trigger').first().json.callback_query?.message?.chat?.id ??
    (() => { try { return $('Parse Shop Selection').first().json.chat_id; } catch (e) { return null; } })() ??
    (() => { try { return $('Extract User Query').first().json.chat_id; } catch (e) { return null; } })()
  );
}

const items = $input.all();
const fallbackShop = getShopId();

for (const item of items) {
  let text = item.json.text;
  if (text === undefined || text === null) {
    text = $('Telegram Trigger').first().json.message?.text || '';
  }
  item.json.normalized = normalizePersian(text);
  item.json.shop_id = item.json.shop_id || fallbackShop;
  item.json.chat_id = item.json.chat_id || getChatId();
}

return items;"""

# ── 2. Aggregate: use rewritten query for RAG answer context ───────────────
find_node(wf, "Aggregate & Filter Matches")["parameters"]["jsCode"] = """const SIMILARITY_THRESHOLD = 0.7;

const allMatches = $input.all().map(item => item.json);
const relevant = allMatches
  .filter(m => (m.similarity ?? 0) >= SIMILARITY_THRESHOLD)
  .sort((a, b) => b.similarity - a.similarity);

let userQuestion = $('Normalize').first().json.normalized;
let originalQuery = userQuestion;
try {
  const prep = $('Prepare Query For Embedding').first().json;
  if (prep.normalized) userQuestion = prep.normalized;
  if (prep.original_query) originalQuery = prep.original_query;
} catch (e) {}

return [{
  json: {
    matches: relevant,
    hasMatches: relevant.length > 0,
    chat_id: $('Normalize').first().json.chat_id,
    user_question: userQuestion,
    original_query: originalQuery
  }
}];"""

find_node(wf, "Build Context")["parameters"]["jsCode"] = """const contextBlock = $json.matches
  .map((m, i) => `${i + 1}. ${m.content}`)
  .join('\\n\\n');

return [{
  json: {
    context: contextBlock,
    user_question: $json.user_question,
    original_query: $json.original_query || $json.user_question,
    chat_id: $json.chat_id
  }
}];"""

# ── 3. Save Pending Query → RPC upsert (safe JSON) ───────────────────────
find_node(wf, "Save Pending Query")["parameters"] = {
    "method": "POST",
    "url": "https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/rpc/upsert_pending_query",
    "authentication": "genericCredentialType",
    "genericAuthType": "httpHeaderAuth",
    "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
    "sendBody": True,
    "specifyBody": "json",
    "jsonBody": '={\n  "p_chat_id": {{ $json.chat_id }},\n  "p_query": {{ JSON.stringify($json.pending_query) }},\n  "p_voice_file_id": {{ JSON.stringify($json.voice_file_id || null) }}\n}',
    "options": {},
}

# ── 4. Save Chat Session: merge upsert preserving pending_query ───────────
find_node(wf, "Save Chat Session")["parameters"]["url"] = (
    "https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/chat_sessions?on_conflict=chat_id"
)
find_node(wf, "Save Chat Session")["parameters"]["headerParameters"] = {
    "parameters": [
        {"name": "Prefer", "value": "resolution=merge-duplicates,return=minimal"},
        {"name": "Content-Type", "value": "application/json"},
    ]
}

# ── 5. Fetch Chat History → RPC get_recent_chat_history ──────────────────
find_node(wf, "Fetch Chat History")["parameters"] = {
    "method": "POST",
    "url": "https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/rpc/get_recent_chat_history",
    "authentication": "genericCredentialType",
    "genericAuthType": "httpHeaderAuth",
    "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
    "sendBody": True,
    "specifyBody": "json",
    "jsonBody": "={\n  \"p_chat_id\": {{ $('Normalize').first().json.chat_id }},\n  \"p_limit\": 4\n}",
    "options": {},
}
find_node(wf, "Fetch Chat History")["alwaysOutputData"] = True

find_node(wf, "Rewrite Query Prompt")["parameters"]["jsCode"] = """const history = $input.all().map(item => item.json);
const originalQuery = $('Normalize').first().json.normalized;

if (!history.length || !history.some(h => h.content && h.content.trim())) {
  return [{ json: { bypass: true, original_query: originalQuery } }];
}

const historyStr = [...history].reverse()
  .map(h => `${h.role === 'user' ? 'کاربر' : 'دستیار'}: ${h.content}`)
  .join('\\n');

return [{ json: { bypass: false, original_query: originalQuery, history: historyStr } }];"""

find_node(wf, "Rewrite Query LLM")["parameters"]["jsonBody"] = (
    '={\n  "model": "llama-3.3-70b-versatile",\n  "temperature": 0.1,\n'
    '  "messages": [\n    {\n      "role": "system",\n'
    '      "content": "شما دستیاری هستید که آخرین پرسش کاربر را به زبان فارسی بر اساس تاریخچه گفتگو بازنویسی می‌کنید تا خودکفا و برای جستجو در پایگاه داده بردار مناسب باشد. اگر پرسش آخر کاربر خودکفا است و به پیام‌های قبلی اشاره ندارد (مثلاً رنگ‌های آن، موجودی این و...)، دقیقاً همان را برگردانید. هیچ توضیح یا مقدمه‌ای اضافه نکنید، فقط پرسش بازنویسی شده را به فارسی خروجی دهید."\n'
    '    },\n    {\n      "role": "user",\n'
    '      "content": {{ JSON.stringify("تاریخچه گفتگو:\\n" + $json.history + "\\n\\nآخرین پرسش:\\n" + $json.original_query) }}\n'
    '    }\n  ]\n}'
)

find_node(wf, "Prepare Query For Embedding")["parameters"]["jsCode"] = """let query = $('Normalize').first().json.normalized;
const original = query;
try {
  const rewritten = $('Rewrite Query LLM').first().json.choices[0].message.content;
  if (rewritten && rewritten.trim()) query = rewritten.trim();
} catch (e) {}

return [{
  json: {
    normalized: query,
    original_query: original,
    shop_id: $('Normalize').first().json.shop_id,
    chat_id: $('Normalize').first().json.chat_id
  }
}];"""

find_node(wf, "Gemini Embed Query")["parameters"]["jsonBody"] = (
    '={\n  "model": "models/gemini-embedding-001",\n  "content": {\n'
    '    "parts": [{ "text": {{ JSON.stringify($(\'Prepare Query For Embedding\').first().json.normalized) }} }]\n  }\n}'
)

# ── 6. Send Fallback: inline keyboard ──────────────────────────────────────
find_node(wf, "Send Fallback")["parameters"]["additionalFields"] = {
    "appendAttribution": False,
    "replyMarkup": "inlineKeyboard",
    "inlineKeyboard": {
        "rows": [
            {"row": {"buttons": [{"text": "📞 پشتیبانی", "additionalFields": {"url": "https://t.me/support_placeholder"}}]}},
            {"row": {"buttons": [{"text": "🔄 تغییر فروشگاه", "additionalFields": {"callbackData": "/changeshop"}}]}},
            {"row": {"buttons": [{"text": "❓ سوالات متداول", "additionalFields": {"callbackData": "faq"}}]}},
        ]
    },
}

# ── 7. Send Shop Confirmed: category discovery buttons ───────────────────
find_node(wf, "Send Shop Confirmed")["parameters"]["additionalFields"] = {
    "replyMarkup": "inlineKeyboard",
    "inlineKeyboard": {
        "rows": [
            {
                "row": {
                    "buttons": [
                        {"text": "کفش👟", "additionalFields": {"callbackData": "search:کفش"}},
                        {"text": "لباس👕", "additionalFields": {"callbackData": "search:لباس"}},
                        {"text": "لوازم جانبی🎒", "additionalFields": {"callbackData": "search:لوازم جانبی"}},
                    ]
                }
            }
        ]
    },
}

# ── 8. Clear pending includes voice file id ────────────────────────────────
find_node(wf, "Clear Pending Query DB")["parameters"]["jsonBody"] = (
    '{\n  "pending_query": null,\n  "pending_voice_file_id": null\n}'
)

find_node(wf, "Clear Pending Query DB")["parameters"]["url"] = (
    "=https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/chat_sessions?chat_id=eq.{{ $('Parse Shop Selection').first().json.chat_id }}"
)

# ── 9. Check Pending Query reads from Get Pending Query node ───────────────
find_node(wf, "Check Pending Query")["parameters"]["conditions"]["conditions"][0]["leftValue"] = (
    "={{ $('Get Pending Query').first().json.pending_query }}"
)

find_node(wf, "Prepare Pending Query For RAG")["parameters"]["jsCode"] = """const pending = $('Get Pending Query').first().json;
return [{
  json: {
    text: pending.pending_query,
    shop_id: pending.shop_id || $('Save Chat Session').first().json?.shop_id,
    chat_id: pending.chat_id || $('Parse Shop Selection').first().json.chat_id,
    pending_voice_file_id: pending.pending_voice_file_id
  }
}];"""

# ── 10. Get Voice File: also works for deferred voice pending ─────────────
find_node(wf, "Get Voice File")["parameters"]["fileId"] = (
    "={{ $('Telegram Trigger').first().json.message?.voice?.file_id ?? $('Prepare Pending Query For RAG').first().json.pending_voice_file_id }}"
)

# ── 11. Send Typing/Upload Voice — n8n requires resource=message for sendChatAction ──
for name, action, pos, use_http in [
    ("Send Typing Action", "typing", [46464, 16144], False),
    ("Send Upload Voice Action", "upload_voice", [46112, 15744], True),
    ("Send Typing Pending RAG", "typing", [46048, 16896], False),
    ("Send Record Voice Pending", "record_voice", [46048, 16640], True),
    ("Send Typing Before LLM", "typing", [48352, 15856], False),
    ("Send Category Typing", "typing", [45792, 16912], False),
]:
    n = find_node(wf, name)
    if not n:
        continue
    if use_http:
        chat_expr = (
            "={{ $('Telegram Trigger').first().json.message?.chat?.id ?? "
            "$('Telegram Trigger').first().json.callback_query?.message?.chat?.id }}"
        )
        if name == "Send Record Voice Pending":
            chat_expr = "={{ $('Parse Shop Selection').first().json.chat_id }}"
        n["type"] = "n8n-nodes-base.httpRequest"
        n["typeVersion"] = 4.4
        n["parameters"] = {
            "method": "POST",
            "url": "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendChatAction",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": f'={{\n  "chat_id": {chat_expr.replace("={{", "{{").replace("}}", "}}")},\n  "action": "{action}"\n}}',
            "options": {},
        }
        n.pop("credentials", None)
    else:
        n["type"] = "n8n-nodes-base.telegram"
        n["typeVersion"] = 1.2
        n["credentials"] = TG_CRED
        chat_id = CHAT_ID
        if name == "Send Typing Pending RAG":
            chat_id = "={{ $('Parse Shop Selection').first().json.chat_id }}"
        elif name == "Send Typing Before LLM":
            chat_id = "={{ $('Build Context').first().json.chat_id }}"
        elif name == "Send Category Typing":
            chat_id = "={{ $('Set Category For RAG').first().json.chat_id }}"
        n["parameters"] = {
            "resource": "message",
            "operation": "sendChatAction",
            "chatId": chat_id,
            "action": "typing",
        }
    n["position"] = pos
    n["onError"] = "continueRegularOutput"
    n.pop("webhookId", None)

# ── 12. New nodes ──────────────────────────────────────────────────────────
NEW_NODES = [
    {
        "parameters": {
            "jsCode": """const msg = $('Telegram Trigger').first().json.message;
const chat_id = msg?.chat?.id;

let pending_query = null;
let voice_file_id = null;

if (msg?.voice?.file_id) {
  pending_query = '__VOICE__';
  voice_file_id = msg.voice.file_id;
} else if (msg?.text) {
  pending_query = msg.text;
}

return [{ json: { chat_id, pending_query, voice_file_id } }];"""
        },
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [45792, 16192],
        "id": "e1a2b3c4-d5e6-4789-a012-3456789abcde",
        "name": "Extract User Query",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                "conditions": [{
                    "id": "has-pending-q",
                    "leftValue": "={{ $json.pending_query }}",
                    "rightValue": "",
                    "operator": {"type": "string", "operation": "notEmpty", "singleValue": True},
                }],
                "combinator": "and",
            },
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.3,
        "position": [46016, 16192],
        "id": "f2b3c4d5-e6f7-4890-b123-456789abcdef",
        "name": "Should Save Pending?",
    },
    {
        "parameters": {
            "url": "=https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/chat_sessions?chat_id=eq.{{ $('Parse Shop Selection').first().json.chat_id }}&select=chat_id,shop_id,pending_query,pending_voice_file_id",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Accept", "value": "application/json"}]},
            "options": {},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": [45248, 16560],
        "id": "a3b4c5d6-e7f8-4901-c234-56789abcdef0",
        "name": "Get Pending Query",
        "alwaysOutputData": True,
        "credentials": SUPA_CRED,
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                "conditions": [{
                    "id": "is-voice-pending",
                    "leftValue": "={{ $('Get Pending Query').first().json.pending_query }}",
                    "rightValue": "__VOICE__",
                    "operator": {"type": "string", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.3,
        "position": [45600, 16768],
        "id": "b4c5d6e7-f890-4012-d345-6789abcdef01",
        "name": "Is Pending Voice?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "ps1", "name": "shop_id", "value": "={{ $('Get Pending Query').first().json.shop_id || $('Parse Shop Selection').first().json.data }}", "type": "string"},
                    {"id": "ps2", "name": "chat_id", "value": "={{ $('Parse Shop Selection').first().json.chat_id }}", "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [45824, 16768],
        "id": "c5d6e7f8-9012-4123-e456-789abcdef012",
        "name": "Set Pending Shop ID",
    },
    {
        "parameters": {
            "resource": "chat",
            "operation": "sendChatAction",
            "chatId": "={{ $('Parse Shop Selection').first().json.chat_id }}",
            "action": "typing",
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [46048, 16896],
        "id": "d6e7f890-1234-4234-f567-89abcdef0123",
        "name": "Send Typing Pending RAG",
        "credentials": TG_CRED,
    },
    {
        "parameters": {
            "resource": "chat",
            "operation": "sendChatAction",
            "chatId": "={{ $('Parse Shop Selection').first().json.chat_id }}",
            "action": "record_voice",
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [46048, 16640],
        "id": "e7f89012-3456-4345-a678-9abcdef01234",
        "name": "Send Record Voice Pending",
        "credentials": TG_CRED,
    },
    {
        "parameters": {
            "resource": "chat",
            "operation": "sendChatAction",
            "chatId": "={{ $('Build Context').first().json.chat_id }}",
            "action": "typing",
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [48352, 15856],
        "id": "f8901234-5678-4456-b789-abcdef012345",
        "name": "Send Typing Before LLM",
        "credentials": TG_CRED,
    },
    {
        "parameters": {
            "url": "=https://aaugvkrnnftgmorjpnoj.supabase.co/rest/v1/chat_sessions?chat_id=eq.{{ $('Prepare Category Search').first().json.chat_id }}&select=chat_id,shop_id",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Accept", "value": "application/json"}]},
            "options": {},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": [45360, 16912],
        "id": "01234567-8901-4789-e012-cdef01234567",
        "name": "Lookup Category Session",
        "alwaysOutputData": True,
        "credentials": SUPA_CRED,
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "cat1", "name": "text", "value": "={{ $('Prepare Category Search').first().json.text }}", "type": "string"},
                    {"id": "cat2", "name": "shop_id", "value": "={{ $json.shop_id }}", "type": "string"},
                    {"id": "cat3", "name": "chat_id", "value": "={{ $('Prepare Category Search').first().json.chat_id }}", "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [45568, 16912],
        "id": "89012345-6789-4567-c890-abcdef0123456",
        "name": "Set Category For RAG",
    },
    {
        "parameters": {
            "resource": "chat",
            "operation": "sendChatAction",
            "chatId": "={{ $('Set Category For RAG').first().json.chat_id }}",
            "action": "typing",
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [45792, 16912],
        "id": "90123456-7890-4678-d901-bcdef01234567",
        "name": "Send Category Typing",
        "credentials": TG_CRED,
    },
]

existing_names = {n["name"] for n in wf["nodes"]}
for node in NEW_NODES:
    if node["name"] not in existing_names:
        wf["nodes"].append(node)

find_node(wf, "Set Text From Voice")["parameters"]["assignments"]["assignments"] = [
    {"id": "96ac7bff-0267-4f1d-9e3b-18762536b04b", "name": "text", "value": "={{ $json.text }}", "type": "string"},
    {"id": "3dfc24e5-f5c1-4e2c-86ab-914aed177582", "name": "chat_id", "value": "={{\n$('Telegram Trigger').first().json.message?.chat?.id ??\n$('Telegram Trigger').first().json.callback_query?.message?.chat?.id ??\n$('Set Pending Shop ID').first().json.chat_id\n}}", "type": "string"},
    {"id": "5d4a1f13-ac4f-4180-a5d7-e23391d9c28d", "name": "shop_id", "value": "={{ $('Set Shop ID From Session').first().json.shop_id || $('Set Pending Shop ID').first().json.shop_id || $('Lookup Chat Session').first().json.shop_id }}", "type": "string"},
]

# Save user message uses original query
find_node(wf, "Save User Message DB")["parameters"]["jsonBody"] = (
    '={\n  "chat_id": {{ $(\'Normalize\').first().json.chat_id }},\n'
    '  "role": "user",\n'
    '  "message": {{ JSON.stringify($(\'Normalize\').first().json.normalized) }}\n}'
)

find_node(wf, "Save Assistant Message DB")["parameters"]["jsonBody"] = (
    '={\n  "chat_id": {{ $(\'Build Context\').first().json.chat_id }},\n'
    '  "role": "assistant",\n'
    '  "message": {{ JSON.stringify($(\'Groq Llama\').first().json.choices[0].message.content) }}\n}'
)

find_node(wf, "Save Fallback Message DB")["parameters"]["jsonBody"] = (
    '={\n  "chat_id": {{ $(\'Normalize\').first().json.chat_id }},\n'
    '  "role": "assistant",\n'
    '  "message": "متأسفم، اطلاع دقیقی در این مورد ندارم. لطفاً با پشتیبانی تماس بگیرید."\n}'
)

# ── 13. Rewire connections ─────────────────────────────────────────────────
C = wf["connections"]

# No session: extract & cache query BEFORE shop picker (not after voice pipeline)
C["Has Active Session?"]["main"][1] = [{"node": "Extract User Query", "type": "main", "index": 0}]
C["Extract User Query"] = {"main": [[{"node": "Should Save Pending?", "type": "main", "index": 0}]]}
C["Should Save Pending?"] = {
    "main": [
        [{"node": "Save Pending Query", "type": "main", "index": 0}],
        [{"node": "Fetch Shops", "type": "main", "index": 0}],
    ]
}
C["Save Pending Query"]["main"] = [[{"node": "Fetch Shops", "type": "main", "index": 0}]]

# Shop selection: fetch pending after save, then route
C["Save Chat Session"]["main"] = [[{"node": "Get Pending Query", "type": "main", "index": 0}]]
C["Get Pending Query"] = {"main": [[{"node": "Answer Callback Query", "type": "main", "index": 0}]]}
C["Answer Callback Query"]["main"] = [[{"node": "Check Pending Query", "type": "main", "index": 0}]]

C["Check Pending Query"]["main"] = [
    [{"node": "Is Pending Voice?", "type": "main", "index": 0}],
    [{"node": "Send Shop Confirmed", "type": "main", "index": 0}],
]

C["Is Pending Voice?"] = {
    "main": [
        [{"node": "Send Record Voice Pending", "type": "main", "index": 0}],
        [{"node": "Clear Pending Query DB", "type": "main", "index": 0}],
    ]
}

C["Send Record Voice Pending"] = {"main": [[{"node": "Set Pending Shop ID", "type": "main", "index": 0}]]}
C["Set Pending Shop ID"] = {"main": [[{"node": "Get Voice File", "type": "main", "index": 0}]]}

C["Clear Pending Query DB"]["main"] = [[{"node": "Send Typing Pending RAG", "type": "main", "index": 0}]]
C["Send Typing Pending RAG"] = {"main": [[{"node": "Prepare Pending Query For RAG", "type": "main", "index": 0}]]}
C["Prepare Pending Query For RAG"]["main"] = [[{"node": "Normalize", "type": "main", "index": 0}]]

# Active session RAG path unchanged except typing before LLM
C["Build Context"]["main"] = [[{"node": "Send Typing Before LLM", "type": "main", "index": 0}]]
C["Send Typing Before LLM"] = {"main": [[{"node": "Groq Llama", "type": "main", "index": 0}]]}

# Remove Check Active Session gate on Normalize path — session already validated upstream
C["Normalize"]["main"] = [[{"node": "Fetch Chat History", "type": "main", "index": 0}]]

# Category search: dedicated lookup → set text/shop → typing → RAG
C["Prepare Category Search"]["main"] = [[{"node": "Lookup Category Session", "type": "main", "index": 0}]]
C["Lookup Category Session"] = {"main": [[{"node": "Set Category For RAG", "type": "main", "index": 0}]]}
C["Set Category For RAG"] = {"main": [[{"node": "Send Category Typing", "type": "main", "index": 0}]]}
C["Send Category Typing"] = {"main": [[{"node": "Normalize", "type": "main", "index": 0}]]}

wf["versionId"] = "cx-fixes-v2-complete"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print(f"Fixed workflow written to {OUT}")
print(f"Total nodes: {len(wf['nodes'])}")
