from flask import Flask, request
import requests
import os
import json
import time
import re

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# ✅ 强制结构输出 Prompt
PROMPT_BOTH = """
请把用户输入的内容整理流畅，并翻译成：

【JP】
自然日本女性敬语表达，需要时可自然加入🙇表示尊重。

【KR】
自然韩国敬语表达，不要添加表情。

必须严格按照以下格式输出：

JP: 日文翻译
KR: 韩文翻译

不要添加解释，不要多余文字。
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
        "model": "gpt-4o-mini",   # ✅ 更省成本更稳定
        "messages": [
            {"role": "system", "content": PROMPT_BOTH},
            {"role": "user", "content": text[:800]},  # ✅ 防止超长炸额度
        ],
        "temperature": 0.1,  # ✅ 翻译类降低随机性
    }

    try:
        resp = requests.post(url, headers=headers, json=data, timeout=20)
        if resp.status_code != 200:
            return None, None

        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()

        # ✅ 强制解析 JP / KR
        jp_match = re.search(r"JP:\s*(.*)", content)
        kr_match = re.search(r"KR:\s*(.*)", content)

        jp = jp_match.group(1).strip() if jp_match else ""
        kr = kr_match.group(1).strip() if kr_match else ""

        return jp, kr

    except Exception as e:
        print("OpenAI error:", e, flush=True)
        return None, None


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

            # ✅ 两个气泡发送
            messages = [{"type": "text", "text": jp_text}]

            if kr_text:
                messages.append({"type": "text", "text": kr_text})

            reply_data = {
                "replyToken": reply_token,
                "messages": messages,
            }

            try:
                requests.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers,
                    json=reply_data,
                    timeout=10,
                )
            except Exception as e:
                print("LINE reply error:", e, flush=True)

    print("Webhook handled in", round(time.time() - start, 3), "sec", flush=True)
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
