#!/usr/bin/env python3
"""
주식 뉴스 분석 → 두레이 전송
장 시작 전 뉴스 분석으로 관심 종목 추천
"""

import requests
import subprocess
import os
from datetime import datetime
import urllib.parse

# 설정
DOORAY_WEBHOOK = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"

def get_market_news():
    """주요 경제/주식 뉴스 가져오기"""
    news_sources = [
        "https://news.hada.io/rss/news",  # GeekNews (기술)
    ]

    news_items = []

    # GeekNews에서 기술 관련 뉴스
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(news_sources[0], timeout=30)
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', ns)[:5]:
            title = entry.find('atom:title', ns)
            if title is not None:
                news_items.append(title.text)
    except:
        pass

    return news_items

def analyze_with_ai(news_items):
    """AI로 주식 관련 분석"""
    if not news_items:
        return "뉴스를 가져오지 못했습니다."

    news_text = "\n".join([f"- {item}" for item in news_items])

    prompt = f"""당신은 주식 애널리스트입니다. 오늘의 뉴스를 분석하여 한국 주식 시장에 영향을 줄 수 있는 내용을 정리해주세요.

오늘의 주요 뉴스:
{news_text}

다음 형식으로 분석해주세요:

1. 시장 전망 (한 줄 요약)

2. 관심 섹터
   - 긍정적: [섹터명] - 이유
   - 부정적: [섹터명] - 이유

3. 관련 종목 (한국 상장)
   - [종목명]: 관심 이유

4. 오늘의 투자 포인트
   - 핵심 한 줄

주의: 이것은 투자 조언이 아닌 뉴스 분석입니다.
"""

    try:
        # Pollinations AI 사용 (느리지만 무료)
        encoded = urllib.parse.quote(prompt)
        url = f"https://text.pollinations.ai/{encoded}?model=openai-fast"
        resp = requests.get(url, timeout=180)
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
        return f"분석 실패: {e}"

def get_market_indices():
    """주요 지수 정보 (하드코딩 예시 - 실제로는 API 필요)"""
    # 실제 구현시 증권 API 연동 필요
    return """
📊 주요 지수 (전일 대비)
  코스피: 상승 예상
  코스닥: 상승 예상
  나스닥: +0.91%
  S&P500: +0.40%
  달러/원: 1,432원 (-0.71%)
"""

def send_to_dooray(analysis):
    """두레이로 전송"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    weekday = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]

    indices = get_market_indices()

    message = f"""📈 {today} ({weekday}) 장 시작 전 브리핑

{indices}
━━━━━━━━━━━━━━━━━━━━

{analysis[:2000]}

━━━━━━━━━━━━━━━━━━━━

⚠️ 본 내용은 뉴스 분석이며 투자 권유가 아닙니다.
"""

    payload = {
        "botName": "주식브리핑",
        "botIconImage": "https://em-content.zobj.net/source/apple/391/chart-increasing_1f4c8.png",
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
    print(f"[{datetime.now()}] 주식 분석 시작")

    # 1. 뉴스 가져오기
    print("뉴스 수집 중...")
    news = get_market_news()
    print(f"뉴스 {len(news)}개 수집")

    # 2. AI 분석
    print("AI 분석 중... (시간 소요)")
    analysis = analyze_with_ai(news)
    print(f"분석 완료: {len(analysis)}자")

    # 3. 두레이 전송
    print("두레이 전송 중...")
    success = send_to_dooray(analysis)

    if success:
        print("✅ 완료!")
    else:
        print("❌ 전송 실패")

if __name__ == "__main__":
    main()
