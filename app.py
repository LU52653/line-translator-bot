from flask import Flask, request
import requests
import os
import json
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# ✅ 一个 Prompt 同时生成日文 + 韩文
PROMPT_BOTH = """
请把用户输入的内容整理流畅，并翻译成：

第一行：自然日本女性敬语表达，需要时可自然加入🙇表示尊重。
第二行：自然韩国敬语表达，不要添加表情。

只输出两行结果，不要解释，不要多余文字。
""".strip()


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


def call_openai(text: str):
    if not OPENAI_API_KEY:
        return None, None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": PROMPT_BOTH},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=data, timeout=20)

    if resp.status_code != 200:
        return None, None

    result = resp.json()
    content = result["choices"][0]["message"]["content"].strip()

    # 拆分成两行
    lines = content.split("\n")
    if len(lines) >= 2:
        jp = lines[0].strip()
        kr = lines[1].strip()
    else:
        jp = content
        kr = ""

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
                jp_text = "请输入要翻译的内容"
                kr_text = ""
            else:
                jp_text, kr_text = call_openai(user_text)

                if not jp_text:
                    jp_text = "翻译服务暂时不可用"
                    kr_text = ""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            }

            # ✅ 两个 message 分开发送（两个气泡）
            messages = [
                {"type": "text", "text": jp_text}
            ]

            if kr_text:
                messages.append({"type": "text", "text": kr_text})

            reply_data = {
                "replyToken": reply_token,
                "messages": messages,
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
