from flask import Flask, request
import requests
import os
import json
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

PROMPT_JP = """
请把用户输入的内容整理流畅，
翻译成自然的日本女性敬语表达。
语气成熟、稳重、有礼貌。
在需要表示尊重时可以自然加入🙇。
只输出翻译结果。
""".strip()

PROMPT_KR = """
请把用户输入的内容整理流畅，
翻译成自然的韩国敬语表达。
语气成熟、稳重、有礼貌。
不要添加任何表情或说明。
只输出翻译结果。
""".strip()


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


def call_openai(text: str, system_prompt: str) -> str:
    if not OPENAI_API_KEY:
        return "翻译服务未配置"

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=data, timeout=20)

    if resp.status_code != 200:
        return "翻译服务暂时不可用"

    result = resp.json()
    return result["choices"][0]["message"]["content"].strip()


def translate_both(text: str):
    jp = call_openai(text, PROMPT_JP)
    kr = call_openai(text, PROMPT_KR)
    return jp, kr


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
            user_text = event.get("message", {}).get("text", "").strip()

            if not user_text:
                final_text = "请输入要翻译的内容"
            else:
                jp_text, kr_text = translate_both(user_text)
                # 分成两个段落
                final_text = f"{jp_text}\n\n{kr_text}"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            }

            reply_data = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": final_text
                    }
                ],
            }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                json=reply_data,
                timeout=10,
            )

    print("Webhook handled in", round(time.time() - start, 3), "sec", flush=True)
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
