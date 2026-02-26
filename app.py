from flask import Flask, request
import requests
import os
import json
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

PROMPT_KR = """
请把用户输入的内容整理流畅，
翻译成30岁韩国女性表达方式的自然敬语。
语气成熟、稳重、有礼貌。
不要添加任何符号、表情、说明。
只输出翻译结果。
""".strip()

PROMPT_JP = """
请把用户输入的内容整理流畅，
翻译成30岁日本女性表达方式的自然敬语（日语敬语）。
语气成熟、稳重、有礼貌。
不要添加任何符号、表情、说明。
只输出翻译结果。
""".strip()


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


def parse_target_and_text(user_text: str):
    t = (user_text or "").strip()
    lower = t.lower()

    if lower.startswith("jp "):
        return "jp", t[3:].strip()
    if lower.startswith("kr "):
        return "kr", t[3:].strip()

    if t.startswith("日 "):
        return "jp", t[2:].strip()
    if t.startswith("韩 "):
        return "kr", t[2:].strip()

    return "kr", t  # 默认韩语


def translate_with_openai(text: str, target: str) -> str:
    if not OPENAI_API_KEY:
        return "暂时无法翻译：未配置OPENAI_API_KEY"

    system_prompt = PROMPT_JP if target == "jp" else PROMPT_KR

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=data, timeout=20)
    result = resp.json()

    if resp.status_code != 200:
        err = result.get("error", {}) if isinstance(result, dict) else {}
        if err.get("code") == "insufficient_quota":
            return "翻译服务额度不足（OpenAI欠费/配额已用完），请充值后再试。"
        return "暂时无法翻译，请稍后再试"

    return result["choices"][0]["message"]["content"].strip()


@app.route("/webhook", methods=["POST"])
def webhook():
    start = time.time()

    body = request.get_data(as_text=True) or ""
    try:
        data = json.loads(body) if body else {}
    except:
        return "OK", 200

    for event in data.get("events", []):
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            reply_token = event.get("replyToken")
            user_text = event.get("message", {}).get("text", "")

            target, cleaned_text = parse_target_and_text(user_text)
            if not cleaned_text:
                translated = "请输入要翻译的内容（例如：kr 你好 / jp 你好）"
            else:
                translated = translate_with_openai(cleaned_text, target)

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
            reply_data = {"replyToken": reply_token, "messages": [{"type": "text", "text": translated}]}

            requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=reply_data, timeout=10)

    print("Webhook handled in", round(time.time() - start, 3), "sec", flush=True)
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
