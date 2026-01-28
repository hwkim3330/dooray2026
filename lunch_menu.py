#!/usr/bin/env python3
"""
판교 테크노밸리 구내식당 점심 메뉴 알림
매일 11시 오늘의 메뉴 두레이로 전송
"""

import requests
from bs4 import BeautifulSoup
import subprocess
import os
import re
from datetime import datetime
from pathlib import Path
import urllib.parse
import pytesseract
from PIL import Image
import io

# 설정
DOORAY_WEBHOOK = "https://keti.dooray.com/services/3711006199900720461/4145226571364668339/1QmQmcTCTMKf3FyF1OemZA"
MENU_DIR = Path("/home/kim/dooray-claude-bot/menus")
MENU_DIR.mkdir(exist_ok=True)

# 판교 테크노밸리 공지사항
PANGYO_URL = "https://www.pangyotechnovalley.org/base/board/list?boardManagementNo=18&menuLevel=2&menuNo=55"

# 요일
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

def get_latest_menu_post():
    """최신 식단표 게시글 찾기"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(PANGYO_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 게시글 목록에서 '식단' 포함된 최신 글 찾기
        for link in soup.find_all('a', href=True):
            text = link.get_text()
            if '식단' in text or '메뉴' in text:
                href = link['href']
                if 'boardNo=' in href:
                    # 상대 경로를 절대 경로로
                    if href.startswith('/'):
                        return f"https://www.pangyotechnovalley.org{href}"
                    return href

        return None
    except Exception as e:
        print(f"게시글 검색 오류: {e}")
        return None

def download_attachments(post_url):
    """게시글에서 첨부파일 다운로드"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(post_url, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')

        files = []
        # 첨부파일 링크 찾기
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()

            if any(ext in text or ext in href.lower() for ext in ['.pdf', '.png', '.jpg', '.jpeg']):
                if href.startswith('/'):
                    href = f"https://www.pangyotechnovalley.org{href}"

                filename = link.get_text().strip()
                if not filename:
                    filename = href.split('/')[-1]

                # 다운로드
                file_resp = requests.get(href, headers=headers, timeout=60)
                filepath = MENU_DIR / filename
                filepath.write_bytes(file_resp.content)
                files.append(filepath)
                print(f"다운로드: {filename}")

        return files
    except Exception as e:
        print(f"첨부파일 다운로드 오류: {e}")
        return []

def ocr_image(image_path):
    """이미지에서 텍스트 추출 (OCR)"""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='kor+eng')
        return text
    except Exception as e:
        print(f"OCR 오류: {e}")
        return ""

def ocr_pdf(pdf_path):
    """PDF에서 텍스트 추출"""
    try:
        # PDF를 이미지로 변환
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # pdftoppm으로 이미지 변환
            subprocess.run([
                'pdftoppm', '-png', '-r', '200',
                str(pdf_path), f'{tmpdir}/page'
            ], check=True, timeout=60)

            # 변환된 이미지들 OCR
            text = ""
            for img_path in sorted(Path(tmpdir).glob('*.png')):
                text += ocr_image(img_path) + "\n"

            return text
    except Exception as e:
        print(f"PDF OCR 오류: {e}")
        return ""

def extract_menu_text(filepath):
    """파일에서 메뉴 텍스트 추출"""
    suffix = filepath.suffix.lower()

    if suffix == '.pdf':
        return ocr_pdf(filepath)
    elif suffix in ['.png', '.jpg', '.jpeg']:
        return ocr_image(filepath)
    else:
        return ""

def parse_today_menu(text, cafeteria_name=""):
    """텍스트에서 오늘 메뉴 추출"""
    today = datetime.now()
    weekday = WEEKDAYS[today.weekday()]
    day = today.day

    # 텍스트 정리
    lines = text.split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    # 오늘 날짜/요일 근처 메뉴 찾기
    menu_lines = []
    found_today = False

    for i, line in enumerate(lines):
        # 오늘 찾기 (날짜 또는 요일)
        if f"{day}일" in line or f"({weekday})" in line or weekday in line:
            found_today = True
            # 다음 몇 줄이 메뉴일 가능성
            for j in range(i, min(i+10, len(lines))):
                menu_lines.append(lines[j])

            # 다음 요일 나오면 중단
            next_weekday = WEEKDAYS[(today.weekday() + 1) % 7]
            if next_weekday in lines[j] if j < len(lines) else False:
                break

    if menu_lines:
        return "\n".join(menu_lines)

    # 못 찾으면 AI에게 요청
    return None

def extract_with_ai(text, cafeteria_name):
    """AI로 오늘 메뉴 추출"""
    today = datetime.now()
    weekday = WEEKDAYS[today.weekday()]
    date_str = today.strftime("%m월 %d일")

    prompt = f"""다음 식단표에서 오늘({date_str} {weekday}요일) 점심 메뉴만 추출해주세요.
식당: {cafeteria_name}

식단표:
{text[:2000]}

형식:
- 메뉴1
- 메뉴2
...

오늘 메뉴가 없으면 "메뉴 정보 없음"이라고 해주세요."""

    try:
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

    return "메뉴 추출 실패"

def get_all_menus():
    """모든 식당 메뉴 가져오기"""
    menus = {}

    # 1. 판교 테크노밸리 (PDF/PNG)
    print("판교 테크노밸리 메뉴 확인 중...")
    post_url = get_latest_menu_post()

    if post_url:
        print(f"게시글: {post_url}")
        files = download_attachments(post_url)

        for filepath in files:
            name = filepath.stem  # 파일명에서 식당명 추출
            print(f"OCR 처리 중: {name}")

            text = extract_menu_text(filepath)
            if text:
                menu = extract_with_ai(text, name)
                menus[name] = menu
    else:
        print("식단표 게시글 못 찾음")

    return menus

def send_to_dooray(menus):
    """두레이로 점심 메뉴 전송"""
    today = datetime.now()
    date_str = today.strftime("%m월 %d일")
    weekday = WEEKDAYS[today.weekday()]

    if not menus:
        menu_text = "오늘 식단 정보를 가져오지 못했습니다."
    else:
        menu_text = ""
        for cafeteria, menu in menus.items():
            menu_text += f"🍽️ {cafeteria}\n{menu}\n\n"

    message = f"""🍴 {date_str} ({weekday}) 오늘의 점심

━━━━━━━━━━━━━━━━━━━━

{menu_text.strip()}

━━━━━━━━━━━━━━━━━━━━

맛있는 점심 되세요! 🍚
"""

    payload = {
        "botName": "점심메뉴",
        "botIconImage": "https://em-content.zobj.net/source/apple/391/fork-and-knife_1f374.png",
        "text": message
    }

    try:
        resp = requests.post(DOORAY_WEBHOOK, json=payload, timeout=10)
        print(f"두레이 전송: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"전송 실패: {e}")
        return False

def main():
    print(f"[{datetime.now()}] 점심 메뉴 봇 시작")

    # 주말 체크
    if datetime.now().weekday() >= 5:
        print("주말은 쉽니다~")
        return

    # 메뉴 가져오기
    menus = get_all_menus()
    print(f"메뉴 {len(menus)}개 식당 수집")

    # 두레이 전송
    send_to_dooray(menus)

if __name__ == "__main__":
    main()
