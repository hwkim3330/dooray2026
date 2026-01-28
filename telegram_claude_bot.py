#!/usr/bin/env python3
"""
텔레그램 Claude 봇
@BotFather에서 봇 생성 후 토큰 사용
"""

import os
import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 설정
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "your-telegram-token")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "your-api-key")

# Claude 클라이언트
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시작 명령"""
    await update.message.reply_text(
        "안녕하세요! Claude 봇입니다.\n"
        "메시지를 보내면 Claude가 답변합니다.\n\n"
        "명령어:\n"
        "/start - 시작\n"
        "/help - 도움말"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말"""
    await update.message.reply_text(
        "사용법: 그냥 메시지를 보내세요!\n"
        "Claude가 답변해드립니다."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """일반 메시지 처리"""
    user = update.effective_user
    text = update.message.text

    print(f"[{user.first_name}] {text}")

    # 타이핑 표시
    await update.message.chat.send_action("typing")

    try:
        # Claude에게 질문
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": text}],
            system=f"당신은 텔레그램 봇입니다. {user.first_name}님의 질문에 간결하고 도움이 되게 한국어로 답변하세요."
        )
        answer = message.content[0].text

        # 텔레그램 메시지 길이 제한 (4096자)
        if len(answer) > 4000:
            answer = answer[:4000] + "...\n\n(응답이 길어서 잘렸습니다)"

        await update.message.reply_text(answer)

    except Exception as e:
        await update.message.reply_text(f"오류 발생: {str(e)}")

def main():
    print("=" * 50)
    print("텔레그램 Claude 봇")
    print("=" * 50)
    print("")
    print("1. @BotFather에서 봇 생성:")
    print("   /newbot → 이름 입력 → 토큰 받기")
    print("")
    print("2. 환경변수 설정:")
    print("   export TELEGRAM_TOKEN='your-token'")
    print("   export ANTHROPIC_API_KEY='your-key'")
    print("")
    print("3. 실행: python3 telegram_claude_bot.py")
    print("=" * 50)

    if TELEGRAM_TOKEN == "your-telegram-token":
        print("\n⚠️  TELEGRAM_TOKEN을 설정하세요!")
        return

    if ANTHROPIC_API_KEY == "your-api-key":
        print("\n⚠️  ANTHROPIC_API_KEY를 설정하세요!")
        return

    # 봇 실행
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("\n봇 시작됨! Ctrl+C로 종료")
    app.run_polling()

if __name__ == "__main__":
    main()
