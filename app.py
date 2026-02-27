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
JP: 日文女性敬语表达（可自然加入🙇，不要标点符号）
KR: 韩文正式书面敬语表达（使用“해 주시기 바랍니다”风格，不要任何符号或表情）

2️⃣ 如果是日文：
输出：
CN: 中文翻译

3️⃣ 如果是韩文：
输出：
CN: 中文翻译

必须严格按照以下格式输出：

JP: xxx
KR: xxx

或者

CN: xxx

不要添加解释，不要多余文字。
""".strip()


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


# ✅ 简单语言判断（优先判断中文）
def detect_language(text):
    if re.search(r'[\u4E00-\u9FFF]', text):
        return "zh"
    elif re.search(r'[\u3040-\u30FF]', text):
        return "jp"
    elif re.search(r'[\uAC00-\uD7A3]', text):
        return "kr"
    return "other"


def call_openai(text: str):
    if not OPENAI_API_KEY:
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    data = {
        "model": "gpt-3.5-turbo",  # 保持3.5
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
        return result["choices"][0]["message"]["content"].strip()

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

            elif re.match(r"您好，请将(\d+)韩元转至其他账户。谢谢。", user_text):
                amount = re.match(
                    r"您好，请将(\d+)韩元转至其他账户。谢谢。",
                    user_text
                ).group(1)

                messages = [{
                    "type": "text",
                    "text": f"안녕하세요 다른 계좌로 {amount}원을 이체해 주시기 바랍니다 감사합니다"
                }]

            else:
                lang = detect_language(user_text)  # ✅ 先本地判断
                result = call_openai(user_text)

                if not result:
                    messages = [{"type": "text", "text": "翻译服务暂时不可用"}]
                else:

                    # ✅ 如果原文是日文或韩文
                    if lang in ["jp", "kr"]:
                        if result.startswith("CN:"):
                            cn_text = result.replace("CN:", "").strip()
                            messages = [{"type": "text", "text": cn_text}]
                        else:
                            messages = [{"type": "text", "text": result}]

                    # ✅ 如果原文是中文（即使模型误返回CN，也强制解析JP/KR）
                    elif lang == "zh":
                        jp_match = re.search(r"JP:\s*(.*)", result)
                        kr_match = re.search(r"KR:\s*(.*)", result)

                        jp_text = jp_match.group(1).strip() if jp_match else ""
                        kr_text = kr_match.group(1).strip() if kr_match else ""

                        jp_text = re.sub(
                            r"[^\u3040-\u30FF\u4E00-\u9FFF🙇\s0-9]",
                            "",
                            jp_text
                        )

                        kr_text = re.sub(
                            r"[^\uAC00-\uD7A3\s0-9]",
                            "",
                            kr_text
                        )

                        messages = []
                        if jp_text:
                            messages.append({"type": "text", "text": jp_text})
                        if kr_text:
                            messages.append({"type": "text", "text": kr_text})

                    else:
                        messages = [{"type": "text", "text": result}]

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
