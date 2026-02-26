from flask import Flask, request
import requests
import os
import json
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

SYSTEM_PROMPT = """
请把用户输入的内容整理流畅，
翻译成30岁韩国女性表达方式的自然敬语。
语气成熟、稳重、有礼貌。
不要添加任何符号、表情、说明。
只输出翻译结果。
""".strip()


def translate_with_openai(text):
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY is missing", flush=True)
        return "暂时无法翻译：未配置OPENAI_API_KEY"

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
    except Exception as e:
        print("OpenAI request exception:", repr(e), flush=True)
        return "暂时无法翻译，请稍后再试"

    print("OpenAI status:", response.status_code, flush=True)
    print("OpenAI raw response:", response.text[:2000], flush=True)

    try:
        result = response.json()
    except Exception as e:
        print("OpenAI json parse error:", repr(e), flush=True)
        return "暂时无法翻译，请稍后再试"

    if response.status_code != 200:
        return "暂时无法翻译，请稍后再试"

    if "choices" in result and result["choices"]:
        return result["choices"][0]["message"]["content"].strip()
    else:
        return "暂时无法翻译，请稍后再试"


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    start = time.time()

    body = request.get_data(as_text=True) or ""
    try:
        data = json.loads(body) if body else {}
    except Exception as e:
        print("Webhook invalid JSON:", repr(e), "body:", body[:500], flush=True)
        return "OK", 200

    for event in data.get("events", []):
        try:
            if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
                reply_token = event.get("replyToken")
                user_text = event.get("message", {}).get("text", "")

                translated = translate_with_openai(user_text)

                if not LINE_CHANNEL_ACCESS_TOKEN:
                    print("LINE_CHANNEL_ACCESS_TOKEN is missing", flush=True)
                    continue

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
                }

                reply_data = {
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": translated}]
                }

                r = requests.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers,
                    json=reply_data,
                    timeout=10
                )
                print("LINE reply status:", r.status_code, flush=True)
                print("LINE reply body:", r.text[:1000], flush=True)

        except Exception as e:
            print("Event handling exception:", repr(e), "event:", str(event)[:1000], flush=True)

    print("Webhook handled in", round(time.time() - start, 3), "sec", flush=True)
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
