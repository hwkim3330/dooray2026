#!/usr/bin/env python3
"""
두레이 슬래시 커맨드 Claude 봇
/c 또는 /ㅊ 명령으로 Claude와 대화
"""

from flask import Flask, request, jsonify
import anthropic
import requests
import os

app = Flask(__name__)

# 설정
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")
DOORAY_WEBHOOK_URL = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"

# Claude 클라이언트
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def send_to_dooray(text, user_name="Claude"):
    """두레이로 메시지 전송"""
    payload = {
        "botName": "Claude Bot",
        "botIconImage": "https://www.anthropic.com/images/icons/apple-touch-icon.png",
        "text": text
    }
    try:
        requests.post(DOORAY_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Dooray 전송 오류: {e}")

def ask_claude(question, user_name):
    """Claude에게 질문"""
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"{question}"
                }
            ],
            system=f"당신은 두레이 메신저에서 동작하는 AI 어시스턴트입니다. {user_name}님의 질문에 간결하고 도움이 되게 답변하세요. 한국어로 답변하세요."
        )
        return message.content[0].text
    except Exception as e:
        return f"오류 발생: {str(e)}"

@app.route("/slash", methods=["POST"])
def handle_slash_command():
    """슬래시 커맨드 처리 (/c, /ㅊ)"""
    try:
        data = request.json or {}

        # 두레이 슬래시 커맨드 데이터 파싱
        user_name = data.get("userName", "사용자")
        command = data.get("command", "")
        text = data.get("text", "").strip()
        channel_id = data.get("channelId", "")

        print(f"[요청] {user_name}: {command} {text}")

        if not text:
            return jsonify({
                "text": "사용법: /c [질문]\n예: /c 파이썬으로 hello world 출력하는 법",
                "responseType": "ephemeral"
            })

        # Claude에게 질문
        answer = ask_claude(text, user_name)

        print(f"[응답] {answer[:100]}...")

        # 채널에 공개 응답
        return jsonify({
            "text": f"**Q: {text}**\n\n{answer}",
            "responseType": "inChannel"
        })

    except Exception as e:
        print(f"오류: {e}")
        return jsonify({
            "text": f"오류가 발생했습니다: {str(e)}",
            "responseType": "ephemeral"
        })

@app.route("/health", methods=["GET"])
def health():
    """헬스 체크"""
    return "OK"

@app.route("/", methods=["GET", "POST"])
def index():
    """기본 엔드포인트"""
    if request.method == "POST":
        return handle_slash_command()
    return "Dooray Claude Bot Running"

if __name__ == "__main__":
    print("=" * 50)
    print("두레이 Claude 봇 서버")
    print("=" * 50)
    print(f"Webhook URL: {DOORAY_WEBHOOK_URL}")
    print("")
    print("실행 전 API 키 설정:")
    print("  export ANTHROPIC_API_KEY='your-key'")
    print("")
    print("두레이 슬래시 커맨드 설정:")
    print("  Request URL: http://YOUR_SERVER:5000/slash")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, debug=True)
