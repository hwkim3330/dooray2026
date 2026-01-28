#!/usr/bin/env python3
"""
브라우저 자동화 에이전트 - Playwright 기반
웹 탐색, 스크린샷, 폼 입력, 클릭 등
"""

import asyncio
import base64
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# 브라우저 상태 저장
BROWSER_DATA_DIR = Path("/home/kim/dooray-claude-bot/agi_data/browser")
BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR = BROWSER_DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


class BrowserAgent:
    """Playwright 기반 브라우저 자동화"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.current_url = None
        self.history = []

    async def start(self, headless: bool = True) -> Dict:
        """브라우저 시작"""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = await self.context.new_page()

            return {"success": True, "message": "브라우저 시작됨"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def stop(self) -> Dict:
        """브라우저 종료"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None
            return {"success": True, "message": "브라우저 종료됨"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def goto(self, url: str, wait_until: str = "networkidle") -> Dict:
        """URL로 이동"""
        if not self.page:
            start_result = await self.start()
            if not start_result["success"]:
                return start_result

        try:
            # URL 정규화
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            await self.page.goto(url, wait_until=wait_until, timeout=30000)
            self.current_url = self.page.url
            self.history.append({
                "url": self.current_url,
                "title": await self.page.title(),
                "time": datetime.now().isoformat()
            })

            return {
                "success": True,
                "url": self.current_url,
                "title": await self.page.title()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, full_page: bool = False) -> Dict:
        """스크린샷 촬영"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = SCREENSHOT_DIR / filename

            await self.page.screenshot(path=str(filepath), full_page=full_page)

            return {
                "success": True,
                "path": str(filepath),
                "url": self.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_text(self) -> Dict:
        """페이지 텍스트 추출"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            text = await self.page.inner_text('body')
            return {
                "success": True,
                "text": text[:5000],
                "url": self.current_url,
                "title": await self.page.title()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str) -> Dict:
        """요소 클릭"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            await self.page.click(selector, timeout=10000)
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            self.current_url = self.page.url

            return {
                "success": True,
                "url": self.current_url,
                "title": await self.page.title()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str) -> Dict:
        """텍스트 입력"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            await self.page.fill(selector, text, timeout=10000)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press_key(self, key: str) -> Dict:
        """키 입력 (Enter, Tab 등)"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            await self.page.keyboard.press(key)
            await asyncio.sleep(0.5)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 500) -> Dict:
        """스크롤"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            if direction == "down":
                await self.page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await self.page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "top":
                await self.page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            return {"success": True, "direction": direction}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_links(self) -> Dict:
        """페이지의 모든 링크 추출"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            links = await self.page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        if (a.href && a.innerText.trim()) {
                            links.push({
                                text: a.innerText.trim().substring(0, 100),
                                href: a.href
                            });
                        }
                    });
                    return links.slice(0, 20);
                }
            """)
            return {"success": True, "links": links}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_google(self, query: str) -> Dict:
        """구글 검색"""
        try:
            result = await self.goto("https://www.google.com")
            if not result["success"]:
                return result

            # 검색창 입력
            await self.page.fill('textarea[name="q"], input[name="q"]', query)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            self.current_url = self.page.url

            # 검색 결과 추출
            results = await self.page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('div.g').forEach(div => {
                        const title = div.querySelector('h3');
                        const link = div.querySelector('a');
                        const snippet = div.querySelector('div[data-sncf], div.VwiC3b');
                        if (title && link) {
                            results.push({
                                title: title.innerText,
                                url: link.href,
                                snippet: snippet ? snippet.innerText.substring(0, 200) : ''
                            });
                        }
                    });
                    return results.slice(0, 5);
                }
            """)

            return {
                "success": True,
                "query": query,
                "results": results,
                "url": self.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_js(self, code: str) -> Dict:
        """JavaScript 실행"""
        if not self.page:
            return {"success": False, "error": "브라우저가 실행 중이 아님"}

        try:
            result = await self.page.evaluate(code)
            return {"success": True, "result": str(result)[:2000]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict:
        """브라우저 상태"""
        return {
            "running": self.page is not None,
            "current_url": self.current_url,
            "history_count": len(self.history)
        }


# 싱글톤 브라우저 인스턴스
browser_agent = BrowserAgent()


# 동기 래퍼 함수들
def browser_goto(url: str) -> Dict:
    """URL로 이동 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.goto(url))
    finally:
        loop.close()


def browser_screenshot() -> Dict:
    """스크린샷 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.screenshot())
    finally:
        loop.close()


def browser_get_text() -> Dict:
    """텍스트 추출 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.get_text())
    finally:
        loop.close()


def browser_click(selector: str) -> Dict:
    """클릭 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.click(selector))
    finally:
        loop.close()


def browser_type(selector: str, text: str) -> Dict:
    """입력 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.type_text(selector, text))
    finally:
        loop.close()


def browser_search(query: str) -> Dict:
    """구글 검색 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.search_google(query))
    finally:
        loop.close()


def browser_links() -> Dict:
    """링크 추출 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.get_links())
    finally:
        loop.close()


def browser_scroll(direction: str = "down") -> Dict:
    """스크롤 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.scroll(direction))
    finally:
        loop.close()


def browser_close() -> Dict:
    """브라우저 종료 (동기)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(browser_agent.stop())
    finally:
        loop.close()


def browser_status() -> Dict:
    """상태 확인"""
    return browser_agent.get_status()
