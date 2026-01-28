#!/usr/bin/env python3
"""
GeekNews 일일 뉴스 요약 → 두레이 전송
매일 아침 자동 실행 (cron)
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import urllib.parse
import subprocess
import os

# 설정
DOORAY_WEBHOOK = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"
RSS_URL = "https://news.hada.io/rss/news"
NEWS_COUNT = 10  # 가져올 뉴스 수

def fetch_news():
    """GeekNews RSS에서 뉴스 가져오기"""
    try:
        resp = requests.get(RSS_URL, timeout=30)
        resp.raise_for_status()

        # XML 파싱 (Atom 피드)
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        news_items = []
        for entry in root.findall('atom:entry', ns)[:NEWS_COUNT]:
            title = entry.find('atom:title', ns)
            link = entry.find('atom:link', ns)
            content = entry.find('atom:content', ns)
            published = entry.find('atom:published', ns)

            news_items.append({
                'title': title.text if title is not None else '',
                'link': link.get('href') if link is not None else '',
                'content': content.text[:300] if content is not None and content.text else '',
                'published': published.text if published is not None else ''
            })

        return news_items
    except Exception as e:
        print(f"뉴스 가져오기 실패: {e}")
        return []

def summarize_with_ai(news_items):
    """AI로 뉴스 요약 (Pollinations.ai openai-fast)"""
    if not news_items:
        return "뉴스를 가져오지 못했습니다."

    # 뉴스 목록 텍스트
    news_text = "\n".join([
        f"{i+1}. {item['title']}"
        for i, item in enumerate(news_items)
    ])

    prompt = f"""다음 IT/개발 뉴스 목록을 한국어로 간단히 요약해주세요.
각 뉴스의 핵심 포인트를 1-2문장으로 요약하고, 개발자들에게 중요한 뉴스는 ⭐로 표시해주세요.

뉴스 목록:
{news_text}

형식:
1. [제목] - 요약
2. [제목] - 요약
...
"""

    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://text.pollinations.ai/{encoded}?model=openai-fast"
        resp = requests.get(url, timeout=120)
        return resp.text.strip()
    except Exception as e:
        # 실패시 로컬 Claude 사용
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "haiku"],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "LANG": "ko_KR.UTF-8"}
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return news_text  # AI 실패시 원본 반환

def send_to_dooray(summary, news_items):
    """두레이로 전송"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    weekday = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]

    # 링크 목록 (깔끔하게)
    links = "\n".join([
        f"  {i+1}. {item['title'][:50]}"
        for i, item in enumerate(news_items[:5])
    ])

    # 마크다운 없이 깔끔한 텍스트
    message = f"""☀️ {today} ({weekday}) 오늘의 개발 뉴스

━━━━━━━━━━━━━━━━━━━━

{summary[:1800]}

━━━━━━━━━━━━━━━━━━━━

📎 주요 링크
{links}

🔗 더보기: news.hada.io
"""

    payload = {
        "botName": "GeekNews",
        "botIconImage": "https://news.hada.io/favicon.ico",
        "text": message
    }

    try:
        resp = requests.post(DOORAY_WEBHOOK, json=payload, timeout=10)
        print(f"두레이 전송: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"두레이 전송 실패: {e}")
        return False

def main():
    print(f"[{datetime.now()}] GeekNews 일일 뉴스 시작")

    # 1. 뉴스 가져오기
    print("뉴스 가져오는 중...")
    news = fetch_news()
    print(f"뉴스 {len(news)}개 가져옴")

    if not news:
        print("뉴스 없음, 종료")
        return

    # 2. AI 요약
    print("AI 요약 중... (느릴 수 있음)")
    summary = summarize_with_ai(news)
    print(f"요약 완료: {len(summary)}자")

    # 3. 두레이 전송
    print("두레이 전송 중...")
    success = send_to_dooray(summary, news)

    if success:
        print("✅ 완료!")
    else:
        print("❌ 전송 실패")

if __name__ == "__main__":
    main()
