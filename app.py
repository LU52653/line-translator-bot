from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def translate_with_openai(text):
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    system_prompt = """
请把用户输入的内容整理流畅，
翻译成30岁韩国女性表达方式的自然敬语。
必须自然、成熟、商务感。
不要添加任何符号、表情、说明。
只输出翻译结果。
"""

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    return result["choices"][0]["message"]["content"]


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    data = json.loads(body)

    for event in data.get("events", []):
        if event["type"] == "message" and event["message"]["type"] == "text":

            reply_token = event["replyToken"]
            user_text = event["message"]["text"]

            translated = translate_with_openai(user_text)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
            }

            reply_data = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": translated
                    }
                ]
            }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                json=reply_data
            )

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
