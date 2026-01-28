# Dooray Claude Bot

두레이 메신저용 Claude AI 봇

## 기능

- `/s [질문]` - Claude에게 질문
- `/s 이미지 [설명]` - AI 이미지 생성 (Pollinations zimage)
- 매일 9:30 GeekNews 요약
- 매일 10:00 주식 뉴스 분석

## 구성

| 파일 | 설명 |
|------|------|
| `dooray_bot_fast.py` | 메인 봇 서버 |
| `daily_news.py` | GeekNews 일일 요약 |
| `stock_analysis.py` | 주식 뉴스 분석 |
| `tunnel_monitor.sh` | 터널 자동 재연결 |

## 실행

```bash
# 봇 서버
python3 dooray_bot_fast.py

# Tailscale Funnel (영구 URL)
sudo tailscale funnel 5000
```

## URL

- Tailscale: `https://kim-system-product-name.tail3bfa88.ts.net/slash`

## 크론 스케줄

```
30 9 * * 1-5  daily_news.py      # 평일 9:30 뉴스
0 10 * * 1-5  stock_analysis.py  # 평일 10:00 주식
```
