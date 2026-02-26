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


@app.route("/", methods=["GET", "HEAD"])
def health():
    return "ok", 200


def translate_with_openai(text: str) -> str:
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY is missing", flush=True)
        return "暂时无法翻译：未配置OPENAI_API_KEY"

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    try:
        resp = requests.post(url, headers=headers, json=data, timeout=20)
    except Exception as e:
        print("OpenAI request exception:", repr(e), flush=True)
        return "暂时无法翻译，请稍后再试"

    print("OpenAI status:", resp.status_code, flush=True)
    print("OpenAI raw response:", resp.text[:2000], flush=True)

    # 先解析 json（即使失败也要兜底）
    try:
        result = resp.json()
    except Exception as e:
        print("OpenAI json parse error:", repr(e), flush=True)
        return "暂时无法翻译，请稍后再试"

    # 非 200：根据错误码给更明确提示
    if resp.status_code != 200:
        err = (result or {}).get("error", {}) if isinstance(result, dict) else {}
        code = err.get("code")
        msg = err.get("message", "")

        if code == "insufficient_quota":
            return "翻译服务额度不足（OpenAI欠费/配额已用完），请充值后再试。"
        if resp.status_code in (401, 403):
            return "翻译服务鉴权失败（OpenAI Key无效或无权限），请检查OPENAI_API_KEY。"
        if resp.status_code == 429:
            return "翻译请求过于频繁或额度不足，请稍后再试。"

        print("OpenAI error code:", code, "message:", msg[:300], flush=True)
        return "暂时无法翻译，请稍后再试"

    # 200：取正常结果
    try:
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("OpenAI response format error:", repr(e), flush=True)
        return "暂时无法翻译，请稍后再试"


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
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                }
                reply_data = {
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": translated}],
                }

                r = requests.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers,
                    json=reply_data,
                    timeout=10,
                )
                print("LINE reply status:", r.status_code, flush=True)
                print("LINE reply body:", r.text[:1000], flush=True)

        except Exception as e:
            print("Event handling exception:", repr(e), "event:", str(event)[:1000], flush=True)

    print("Webhook handled in", round(time.time() - start, 3), "sec", flush=True)
    return "OK", 200


if __name__ == "__main__":
    port_str = os.environ.get("PORT", "10000")
    print("PORT env =", os.environ.get("PORT"), flush=True)
    print("Listening port =", port_str, flush=True)
    app.run(host="0.0.0.0", port=int(port_str))
