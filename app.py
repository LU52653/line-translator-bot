from flask import Flask, request
import requests
import os
import json
import time
import re

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

PROMPT = """
请先判断用户输入的语言。

规则如下：

1️⃣ 如果是中文：
输出：
JP: 日文女性敬语翻译（可自然加入🙇）
KR: 韩文敬语翻译（不要表情）

2️⃣ 如果是日文：
输出：
CN: 中文翻译

3️⃣ 如果是韩文：
输出：
CN: 中文翻译

必须严格按照以下格式输出其中一种：

JP: xxx
KR: xxx

或者

CN: xxx

不要添加解释，不要多余文字。
""".strip()


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


def call_openai(text: str):
    if not OPENAI_API_KEY:
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text[:800]},
        ],
        "temperature": 0.1,
    }

    try:
        resp = requests.post(url, headers=headers, json=data, timeout=20)
        if resp.status_code != 200:
            return None

        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return content

    except Exception as e:
        print("OpenAI error:", e, flush=True)
        return None


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
                messages = [{"type": "text", "text": "请输入内容"}]
            else:
                result = call_openai(user_text)

                if not result:
                    messages = [{"type": "text", "text": "翻译服务暂时不可用"}]
                else:
                    # 判断返回结构
                    if result.startswith("CN:"):
                        # 日语或韩语 → 中文（一个气泡）
                        cn_text = result.replace("CN:", "").strip()
                        messages = [{"type": "text", "text": cn_text}]
                    else:
                        # 中文 → 日文 + 韩文（两个气泡）
                        jp_match = re.search(r"JP:\s*(.*)", result)
                        kr_match = re.search(r"KR:\s*(.*)", result)

                        jp_text = jp_match.group(1).strip() if jp_match else ""
                        kr_text = kr_match.group(1).strip() if kr_match else ""

                        messages = []
                        if jp_text:
                            messages.append({"type": "text", "text": jp_text})
                        if kr_text:
                            messages.append({"type": "text", "text": kr_text})

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            }

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
