#!/bin/bash
# 두레이 Claude 봇 + 터널 자동 실행/재연결

BOT_DIR="/home/kim/dooray-claude-bot"
LOG_DIR="$BOT_DIR/logs"
mkdir -p "$LOG_DIR"

# 봇 서버 실행
start_bot() {
    if ! curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo "[$(date)] 봇 서버 시작..."
        cd "$BOT_DIR"
        nohup python3 dooray_bot_simple.py > "$LOG_DIR/bot.log" 2>&1 &
        sleep 2
    fi
}

# 터널 실행 및 URL 저장
start_tunnel() {
    # 기존 터널 종료
    pkill -f "localhost.run" 2>/dev/null
    sleep 1

    echo "[$(date)] 터널 연결 중..."
    ssh -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -R 80:localhost:5000 \
        nokey@localhost.run 2>&1 | while read line; do
        echo "$line"
        # URL 추출해서 저장
        if echo "$line" | grep -qE "https://.*\.lhr\.life"; then
            URL=$(echo "$line" | grep -oE "https://[a-z0-9]+\.lhr\.life")
            echo "$URL" > "$LOG_DIR/tunnel_url.txt"
            echo "[$(date)] 터널 URL: $URL"
            echo "[$(date)] 두레이 설정: ${URL}/slash"
        fi
    done
}

# 메인 루프
echo "=========================================="
echo "두레이 Claude 봇 시작"
echo "=========================================="

while true; do
    start_bot
    start_tunnel
    echo "[$(date)] 터널 끊김, 10초 후 재연결..."
    sleep 10
done
