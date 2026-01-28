#!/usr/bin/env python3
"""
두레이 Claude 봇 (Claude Code CLI 백엔드)
API 키 없이 Claude 계정으로 사용

Claude Code가 설치되어 있어야 함:
  npm install -g @anthropic-ai/claude-code
"""

from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

# 두레이 웹훅
DOORAY_WEBHOOK_URL = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"

def ask_claude_cli(question):
    """Claude Code CLI를 통해 질문"""
    try:
        # claude CLI 호출 (비대화형 모드)
        result = subprocess.run(
            ["claude", "-p", question, "--no-input"],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "LANG": "ko_KR.UTF-8"}
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"오류: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "응답 시간이 초과되었습니다."
    except FileNotFoundError:
        return "Claude Code CLI가 설치되지 않았습니다. 'npm install -g @anthropic-ai/claude-code' 실행하세요."
    except Exception as e:
        return f"오류: {str(e)}"

@app.route("/slash", methods=["POST"])
def handle_slash():
    """두레이 슬래시 커맨드 처리"""
    try:
        data = request.json or {}

        user_name = data.get("userName", "사용자")
        text = data.get("text", "").strip()
        tenant_domain = data.get("tenantDomain", "")
        channel_name = data.get("channelName", "")

        print(f"[{user_name}@{channel_name}] {text}")

        if not text:
            return jsonify({
                "text": "사용법: /c [질문]\n예: /c 오늘 날씨 어때?",
                "responseType": "ephemeral"
            })

        # Claude Code CLI로 질문
        answer = ask_claude_cli(text)

        print(f"[응답] {answer[:100]}...")

        return jsonify({
            "text": f"**Q: {text}**\n\n{answer}",
            "responseType": "inChannel"
        })

    except Exception as e:
        return jsonify({
            "text": f"오류: {str(e)}",
            "responseType": "ephemeral"
        })

@app.route("/", methods=["GET"])
def index():
    return "Dooray Claude Bot (CLI Backend) Running"

@app.route("/health", methods=["GET"])
def health():
    return "OK"

if __name__ == "__main__":
    print("=" * 50)
    print("두레이 Claude 봇 (계정 연동)")
    print("=" * 50)
    print("")
    print("Claude Code CLI 사용 - API 키 불필요")
    print("")
    print("두레이 슬래시 커맨드 설정:")
    print("  Request URL: http://YOUR_IP:5000/slash")
    print("")
    print("ngrok으로 외부 접속 가능하게:")
    print("  ngrok http 5000")
    print("=" * 50)

    # Claude CLI 확인
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        print(f"\n✓ Claude Code: {result.stdout.strip()}")
    except:
        print("\n⚠️  Claude Code CLI 확인 필요")

    app.run(host="0.0.0.0", port=5000, debug=True)
