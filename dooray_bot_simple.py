#!/usr/bin/env python3
"""
두레이 Claude 봇 서버 (간단 버전)
Claude Code CLI 사용 - API 키 불필요
"""

from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

def ask_claude(question):
    """Claude Code CLI로 질문"""
    try:
        result = subprocess.run(
            ["claude", "-p", question],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "LANG": "ko_KR.UTF-8"}
        )
        if result.returncode == 0:
            answer = result.stdout.strip()
            # 너무 길면 자르기
            if len(answer) > 3000:
                answer = answer[:3000] + "\n\n...(응답 일부 생략)"
            return answer
        return f"오류: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "⏱️ 응답 시간이 초과되었습니다. 더 짧은 질문을 해주세요."
    except FileNotFoundError:
        return "❌ Claude Code CLI가 설치되지 않았습니다."
    except Exception as e:
        return f"❌ 오류: {str(e)}"

@app.route("/slash", methods=["POST"])
def slash():
    """두레이 슬래시 커맨드"""
    data = request.json or {}

    user = data.get("userName", "사용자")
    text = data.get("text", "").strip()
    cmd = data.get("command", "/c")

    print(f"[요청] {user}: {cmd} {text}")

    if not text:
        return jsonify({
            "text": f"💡 사용법: `{cmd} [질문]`\n예: `{cmd} 파이썬 리스트 정렬하는 법`",
            "responseType": "ephemeral"
        })

    answer = ask_claude(text)
    print(f"[응답] {answer[:50]}...")

    return jsonify({
        "text": f"**🙋 {user}:** {text}\n\n**🤖 Claude:**\n{answer}",
        "responseType": "inChannel"
    })

@app.route("/", methods=["GET"])
def home():
    return "✅ Dooray Claude Bot Running"

@app.route("/health", methods=["GET"])
def health():
    return "OK"

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 두레이 Claude 봇 서버")
    print("=" * 50)
    print("Endpoint: http://0.0.0.0:5000/slash")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
