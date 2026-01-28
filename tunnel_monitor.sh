#!/bin/bash
# 터널 자동 감시 및 재연결 스크립트
# 30초마다 체크, 죽으면 재연결

LOG_DIR="/home/kim/dooray-claude-bot/logs"
mkdir -p "$LOG_DIR"

URL_FILE="$LOG_DIR/tunnel_url.txt"
LOG_FILE="$LOG_DIR/tunnel_monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_tunnel() {
    pkill -f "ssh.*localhost.run" 2>/dev/null
    sleep 1

    log "터널 시작 중..."

    ssh -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -R 80:localhost:5000 \
        nokey@localhost.run 2>&1 | while read line; do

        # URL 추출
        if echo "$line" | grep -qE "https://.*\.lhr\.life"; then
            URL=$(echo "$line" | grep -oE "https://[a-z0-9]+\.lhr\.life")
            echo "$URL" > "$URL_FILE"
            log "새 터널 URL: $URL"
            log "두레이 설정: ${URL}/slash"

            # 두레이로 새 URL 알림
            curl -s -X POST "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA" \
                -H "Content-Type: application/json" \
                -d "{\"botName\":\"터널봇\",\"text\":\"🔄 새 터널 URL: ${URL}/slash\n\n두레이 슬래시 커맨드 설정에서 URL 업데이트 필요!\"}" || true
        fi
    done &

    sleep 5
}

check_tunnel() {
    if [ -f "$URL_FILE" ]; then
        URL=$(cat "$URL_FILE")
        RESULT=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$URL/health" 2>/dev/null)
        if [ "$RESULT" = "200" ]; then
            return 0  # 살아있음
        fi
    fi
    return 1  # 죽음
}

check_bot() {
    RESULT=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:5000/health" 2>/dev/null)
    if [ "$RESULT" = "200" ]; then
        return 0
    fi
    return 1
}

start_bot() {
    pkill -f "dooray_bot_fast.py" 2>/dev/null
    sleep 1
    cd /home/kim/dooray-claude-bot
    nohup python3 dooray_bot_fast.py > "$LOG_DIR/bot.log" 2>&1 &
    log "봇 서버 시작됨"
    sleep 2
}

# 메인 루프
log "=========================================="
log "터널 모니터 시작"
log "=========================================="

while true; do
    # 봇 체크
    if ! check_bot; then
        log "봇 죽음 - 재시작"
        start_bot
    fi

    # 터널 체크
    if ! check_tunnel; then
        log "터널 죽음 - 재연결"
        start_tunnel
    fi

    sleep 30
done
