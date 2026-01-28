#!/usr/bin/env python3
"""
실시간 뉴스 모니터링 → 중요 뉴스 즉시 두레이 알림
5분마다 체크, 새 뉴스 발견시 AI 분석 후 알림
"""

import requests
import xml.etree.ElementTree as ET
import subprocess
import os
import json
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

# 설정
DOORAY_WEBHOOK = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"
CHECK_INTERVAL = 1800  # 30분
SEEN_FILE = Path("/home/kim/dooray-claude-bot/logs/seen_news.json")

# 뉴스 소스
NEWS_SOURCES = {
    "GeekNews": "https://news.hada.io/rss/news",
}

# 주식 관련 키워드 (중요한 것만)
STOCK_KEYWORDS = [
    "삼성전자", "SK하이닉스", "엔비디아", "테슬라",
    "금리인상", "금리인하", "연준", "FOMC",
    "IPO", "상장폐지", "인수합병",
    "실적발표", "어닝서프라이즈",
    "트럼프", "관세",
]

# 긴급 키워드 (바로 알림)
URGENT_KEYWORDS = [
    "속보", "긴급", "폭락", "폭등", "급등", "급락", "서킷브레이커",
]

def load_seen():
    """이미 본 뉴스 ID 로드"""
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen):
    """본 뉴스 ID 저장"""
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(list(seen)[-500:]))  # 최근 500개만

def fetch_news():
    """뉴스 가져오기"""
    all_news = []

    for source, url in NEWS_SOURCES.items():
        try:
            resp = requests.get(url, timeout=30)
            root = ET.fromstring(resp.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            for entry in root.findall('atom:entry', ns)[:10]:
                news_id = entry.find('atom:id', ns)
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                content = entry.find('atom:content', ns)

                if news_id is not None and title is not None:
                    all_news.append({
                        'id': news_id.text,
                        'source': source,
                        'title': title.text,
                        'link': link.get('href') if link is not None else '',
                        'content': content.text[:500] if content is not None and content.text else '',
                    })
        except Exception as e:
            print(f"[{source}] 오류: {e}")

    return all_news

def is_stock_related(title, content):
    """주식 관련 뉴스인지 확인"""
    text = title + " " + content

    # 긴급 키워드 먼저 체크
    for keyword in URGENT_KEYWORDS:
        if keyword in text:
            return True, f"🚨{keyword}"

    # 일반 키워드
    for keyword in STOCK_KEYWORDS:
        if keyword in text:
            return True, keyword

    return False, None

def analyze_importance(news_item):
    """AI로 뉴스 중요도 분석"""
    prompt = f"""다음 뉴스가 한국 주식 시장에 미칠 영향을 분석해주세요.

제목: {news_item['title']}
내용: {news_item['content'][:300]}

다음 형식으로 답변:
중요도: (상/중/하)
영향: (긍정/부정/중립)
관련섹터: (섹터명)
관련종목: (한국 상장 종목 1-2개)
한줄요약: (투자자가 알아야 할 핵심)

간단히 답변해주세요."""

    try:
        # 로컬 Claude (빠름)
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "LANG": "ko_KR.UTF-8"}
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass

    return None

def send_alert(news_item, analysis, keyword):
    """두레이로 알림"""
    now = datetime.now().strftime("%H:%M")

    message = f"""🚨 실시간 뉴스 알림 [{now}]

📰 {news_item['title']}

🔑 키워드: {keyword}
📎 출처: {news_item['source']}

━━━━━━━━━━━━━━━━━━━━

{analysis if analysis else '(분석 중...)'}

━━━━━━━━━━━━━━━━━━━━

🔗 {news_item['link']}

⚠️ 투자 판단은 본인 책임입니다.
"""

    payload = {
        "botName": "뉴스알림",
        "botIconImage": "https://em-content.zobj.net/source/apple/391/bell_1f514.png",
        "text": message
    }

    try:
        resp = requests.post(DOORAY_WEBHOOK, json=payload, timeout=10)
        return resp.status_code == 200
    except:
        return False

def main():
    print(f"[{datetime.now()}] 실시간 뉴스 모니터 시작")
    print(f"체크 간격: {CHECK_INTERVAL}초")
    print(f"키워드: {len(STOCK_KEYWORDS)}개")
    print("-" * 50)

    seen = load_seen()

    while True:
        try:
            news_list = fetch_news()
            new_count = 0

            for news in news_list:
                if news['id'] in seen:
                    continue

                # 새 뉴스 발견
                seen.add(news['id'])

                # 주식 관련 체크
                is_related, keyword = is_stock_related(news['title'], news['content'])

                if is_related:
                    print(f"[새 뉴스] {news['title'][:50]}... (키워드: {keyword})")

                    # AI 분석
                    analysis = analyze_importance(news)

                    # 알림 전송
                    if send_alert(news, analysis, keyword):
                        print(f"  → 알림 전송 완료")
                        new_count += 1
                    else:
                        print(f"  → 알림 전송 실패")

            save_seen(seen)

            if new_count == 0:
                print(f"[{datetime.now().strftime('%H:%M')}] 새 뉴스 없음")

        except Exception as e:
            print(f"오류: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
