from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

def translate_text(text):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "ko",
        "dt": "t",
        "q": text
    }
    response = requests.get(url, params=params)
    result = response.json()
    return result[0][0][0]

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    data = json.loads(body)

    for event in data.get("events", []):
        if event["type"] == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            user_text = event["message"]["text"]
            translated = translate_text(user_text)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
            }

            payload = {
                "replyToken": reply_token,
                "messages": [
                    {"type": "text", "text": translated}
                ]
            }

            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                data=json.dumps(payload)
            )

    return "OK"

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
