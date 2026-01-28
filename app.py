#!/usr/bin/env python3
"""
두레이 Claude 봇 - Hugging Face Spaces용
/c 또는 /ㅊ 명령으로 Claude와 대화
"""

import os
import subprocess
import gradio as gr
from flask import Flask, request, jsonify
import threading

# Flask 앱
flask_app = Flask(__name__)

# 두레이 토큰 검증 (선택사항)
DOORAY_TOKEN = os.environ.get("DOORAY_TOKEN", "c58b057b-7ebe-4ff9-9b88-a513346afbac")

def ask_claude(question):
    """Claude CLI로 질문"""
    try:
        result = subprocess.run(
            ["claude", "-p", question, "--no-input"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"오류: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "응답 시간 초과"
    except FileNotFoundError:
        # Claude CLI 없으면 Anthropic API 사용
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": question}]
            )
            return msg.content[0].text
        except Exception as e:
            return f"Claude 연결 오류: {e}"
    except Exception as e:
        return f"오류: {e}"

@flask_app.route("/slash", methods=["POST"])
def handle_slash():
    """두레이 슬래시 커맨드 처리"""
    try:
        data = request.json or {}

        # 토큰 검증 (선택)
        token = data.get("token", "")
        if DOORAY_TOKEN and token and token != DOORAY_TOKEN:
            return jsonify({"text": "인증 실패", "responseType": "ephemeral"})

        user_name = data.get("userName", "사용자")
        text = data.get("text", "").strip()
        command = data.get("command", "/c")

        print(f"[{user_name}] {command} {text}")

        if not text:
            return jsonify({
                "text": f"사용법: {command} [질문]\n예: {command} 파이썬 hello world",
                "responseType": "ephemeral"
            })

        answer = ask_claude(text)

        return jsonify({
            "text": f"**Q: {text}**\n\n{answer}",
            "responseType": "inChannel"
        })

    except Exception as e:
        print(f"오류: {e}")
        return jsonify({"text": f"오류: {e}", "responseType": "ephemeral"})

@flask_app.route("/", methods=["GET"])
def index():
    return "Dooray Claude Bot Running"

@flask_app.route("/health", methods=["GET"])
def health():
    return "OK"

# Gradio 인터페이스 (HF Spaces 필수)
def chat(message, history):
    """Gradio 채팅 인터페이스"""
    return ask_claude(message)

# Flask를 백그라운드에서 실행
def run_flask():
    flask_app.run(host="0.0.0.0", port=7861, debug=False)

if __name__ == "__main__":
    # Flask 서버 시작 (백그라운드)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Gradio 인터페이스 (메인)
    demo = gr.ChatInterface(
        chat,
        title="Claude Bot for Dooray",
        description="두레이 슬래시 커맨드: /c 또는 /ㅊ\n\nAPI Endpoint: /slash",
        examples=["안녕하세요", "파이썬으로 hello world", "오늘 뭐하지?"]
    )
    demo.launch(server_name="0.0.0.0", server_port=7860)
