#!/usr/bin/env python3
"""
AGI 스타일 텔레그램 봇 - Moltbot/Clawd.bot 참고
풀 컴퓨터 접근, 영구 메모리, 도구 시스템, 자율 에이전트
"""

import logging
import subprocess
import os
import json
import urllib.parse
import re
import requests
import asyncio
import base64
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest
from concurrent.futures import ThreadPoolExecutor

# 브라우저 에이전트
from browser_agent import (
    browser_goto, browser_screenshot, browser_get_text,
    browser_click, browser_type, browser_search,
    browser_links, browser_scroll, browser_close, browser_status
)

# ═══════════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8492678625:AAHEmQQAwRyfI9K1d6n_ubigVnrNLAbUzH0"
DATA_DIR = Path("/home/kim/dooray-claude-bot/agi_data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "memory.json"
SKILLS_DIR = DATA_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)

# 허용된 사용자 (비어있으면 모두 허용)
ALLOWED_USERS = []

# 로깅
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 스레드 풀
executor = ThreadPoolExecutor(max_workers=4)


# ═══════════════════════════════════════════════════════════════
# 영구 메모리 시스템
# ═══════════════════════════════════════════════════════════════

class Memory:
    """Moltbot 스타일 영구 메모리 - 모든 것을 기억"""

    def __init__(self):
        self.data = self._load()

    def _load(self) -> Dict:
        if MEMORY_FILE.exists():
            try:
                return json.loads(MEMORY_FILE.read_text())
            except:
                pass
        return {
            "users": {},
            "facts": [],  # 학습된 사실들
            "preferences": {},  # 사용자 선호도
            "skills_used": {},  # 사용된 스킬 통계
            "conversations": {},  # 전체 대화 기록
        }

    def save(self):
        MEMORY_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))

    def get_user(self, user_id: int) -> Dict:
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "name": "",
                "first_seen": datetime.now().isoformat(),
                "last_seen": None,
                "message_count": 0,
                "facts": [],  # 이 사용자에 대해 알게 된 것들
                "preferences": {},
                "history": [],  # 최근 대화
            }
        return self.data["users"][uid]

    def add_message(self, user_id: int, role: str, content: str, metadata: Dict = None):
        user = self.get_user(user_id)
        user["history"].append({
            "role": role,
            "content": content[:1000],
            "time": datetime.now().isoformat(),
            "metadata": metadata or {}
        })
        user["history"] = user["history"][-50:]  # 최근 50개 유지
        user["message_count"] += 1
        user["last_seen"] = datetime.now().isoformat()
        self.save()

    def learn_fact(self, user_id: int, fact: str):
        """사용자에 대한 새로운 사실 학습"""
        user = self.get_user(user_id)
        if fact not in user["facts"]:
            user["facts"].append(fact)
            user["facts"] = user["facts"][-20:]  # 최근 20개
            self.save()

    def get_context(self, user_id: int, limit: int = 10) -> str:
        """대화 컨텍스트 + 학습된 사실"""
        user = self.get_user(user_id)
        context_parts = []

        # 사용자에 대해 알고 있는 것
        if user["facts"]:
            context_parts.append(f"이 사용자에 대해 알고 있는 것: {', '.join(user['facts'][-5:])}")

        if user["preferences"]:
            prefs = ", ".join([f"{k}={v}" for k, v in list(user["preferences"].items())[:5]])
            context_parts.append(f"선호도: {prefs}")

        # 최근 대화
        if user["history"]:
            recent = user["history"][-limit:]
            history_text = "\n".join([
                f"{h['role']}: {h['content'][:200]}" for h in recent
            ])
            context_parts.append(f"최근 대화:\n{history_text}")

        return "\n\n".join(context_parts)


memory = Memory()


# ═══════════════════════════════════════════════════════════════
# 도구 시스템 (Skills)
# ═══════════════════════════════════════════════════════════════

class Tools:
    """AGI 도구 시스템 - 컴퓨터 풀 접근"""

    @staticmethod
    def execute_shell(command: str, timeout: int = 60) -> Dict:
        """셸 명령 실행"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path.home())
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:2000] if result.stdout else "",
                "stderr": result.stderr[:500] if result.stderr else "",
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "타임아웃"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def read_file(path: str) -> Dict:
        """파일 읽기"""
        try:
            p = Path(path).expanduser()
            if p.exists():
                content = p.read_text()[:5000]
                return {"success": True, "content": content}
            return {"success": False, "error": "파일 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def write_file(path: str, content: str) -> Dict:
        """파일 쓰기"""
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {"success": True, "path": str(p)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def web_search(query: str, max_results: int = 5) -> Dict:
        """웹 검색"""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return {
                    "success": True,
                    "results": [
                        {"title": r["title"], "body": r["body"], "url": r["href"]}
                        for r in results
                    ]
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def fetch_url(url: str) -> Dict:
        """URL 내용 가져오기"""
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AGI-Bot/1.0)"
            })
            # HTML을 텍스트로 간단히 변환
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)[:3000]
            return {"success": True, "content": text, "status": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_image(prompt: str) -> str:
        """이미지 생성 URL"""
        encoded = urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true"

    @staticmethod
    def get_system_info() -> Dict:
        """시스템 정보"""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "uptime": str(timedelta(seconds=int(
                    datetime.now().timestamp() - psutil.boot_time()
                )))
            }
        except:
            return {}

    @staticmethod
    def run_python(code: str) -> Dict:
        """파이썬 코드 실행"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ['python3', f.name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                os.unlink(f.name)
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout[:2000],
                    "error": result.stderr[:500] if result.stderr else ""
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def screenshot() -> Optional[bytes]:
        """스크린샷 (Linux)"""
        try:
            result = subprocess.run(
                ['scrot', '-o', '/tmp/screenshot.png'],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                return Path('/tmp/screenshot.png').read_bytes()
        except:
            pass
        return None

    # ═══════════════════════════════════════════════════════════════
    # 브라우저 도구
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def browser_open(url: str) -> Dict:
        """브라우저로 URL 열기"""
        return browser_goto(url)

    @staticmethod
    def browser_capture() -> Dict:
        """브라우저 스크린샷"""
        return browser_screenshot()

    @staticmethod
    def browser_read() -> Dict:
        """브라우저 페이지 텍스트 읽기"""
        return browser_get_text()

    @staticmethod
    def browser_google(query: str) -> Dict:
        """구글 검색"""
        return browser_search(query)

    @staticmethod
    def browser_click_element(selector: str) -> Dict:
        """요소 클릭"""
        return browser_click(selector)

    @staticmethod
    def browser_input(selector: str, text: str) -> Dict:
        """텍스트 입력"""
        return browser_type(selector, text)

    @staticmethod
    def browser_get_links() -> Dict:
        """페이지 링크 목록"""
        return browser_links()

    @staticmethod
    def browser_scroll_page(direction: str = "down") -> Dict:
        """스크롤"""
        return browser_scroll(direction)

    @staticmethod
    def browser_quit() -> Dict:
        """브라우저 종료"""
        return browser_close()

    @staticmethod
    def browser_info() -> Dict:
        """브라우저 상태"""
        return browser_status()


tools = Tools()


# ═══════════════════════════════════════════════════════════════
# Claude 에이전트
# ═══════════════════════════════════════════════════════════════

class ClaudeAgent:
    """Claude 기반 자율 에이전트"""

    SYSTEM_PROMPT = """너는 텔레그램에서 동작하는 강력한 AI 어시스턴트야.

## 성격
- 친근하고 유능함
- 적극적으로 도움을 제공
- 필요하면 도구를 사용해서 실제 작업 수행
- 이모지 적절히 사용

## 사용 가능한 도구
너는 다음 도구들을 사용할 수 있어:

### 시스템 도구
1. **shell**: 셸 명령 실행 (ls, cat, git, docker 등)
2. **read_file**: 파일 읽기
3. **write_file**: 파일 쓰기
4. **python**: 파이썬 코드 실행
5. **system_info**: 시스템 상태 확인

### 웹/검색 도구
6. **web_search**: 웹 검색 (DuckDuckGo)
7. **fetch_url**: 웹페이지 내용 가져오기

### 브라우저 도구 (Playwright)
8. **browser_open**: 브라우저로 URL 열기 {"url": "https://..."}
9. **browser_screenshot**: 현재 페이지 스크린샷
10. **browser_read**: 현재 페이지 텍스트 읽기
11. **browser_google**: 구글 검색 {"query": "검색어"}
12. **browser_click**: 요소 클릭 {"selector": "CSS선택자"}
13. **browser_input**: 텍스트 입력 {"selector": "CSS선택자", "text": "입력값"}
14. **browser_links**: 페이지의 모든 링크 목록
15. **browser_scroll**: 스크롤 {"direction": "down/up/top/bottom"}
16. **browser_close**: 브라우저 종료

### 생성 도구
17. **image**: 이미지 생성 {"prompt": "설명"}

## 도구 사용법
도구를 사용하려면 다음 형식으로 응답해:

```tool
{"tool": "도구이름", "args": {"arg1": "value1"}}
```

예시:
```tool
{"tool": "shell", "args": {"command": "ls -la"}}
```

```tool
{"tool": "web_search", "args": {"query": "파이썬 튜토리얼"}}
```

## 규칙
1. 사용자 요청을 이해하고 필요하면 도구 사용
2. 위험한 명령(rm -rf /, 시스템 파일 삭제 등)은 실행 전 확인
3. 결과를 친절하게 설명
4. 한국어로 대화"""

    @staticmethod
    def parse_tool_calls(response: str) -> List[Dict]:
        """응답에서 도구 호출 파싱"""
        tool_calls = []
        pattern = r'```tool\s*\n?(.*?)\n?```'
        matches = re.findall(pattern, response, re.DOTALL)
        for match in matches:
            try:
                tool_call = json.loads(match.strip())
                if "tool" in tool_call:
                    tool_calls.append(tool_call)
            except:
                pass
        return tool_calls

    @staticmethod
    def execute_tool(tool_name: str, args: Dict) -> str:
        """도구 실행"""
        try:
            if tool_name == "shell":
                result = tools.execute_shell(args.get("command", ""))
                if result["success"]:
                    return f"✅ 실행 완료:\n```\n{result['stdout']}\n```"
                return f"❌ 오류: {result.get('error', result.get('stderr', ''))}"

            elif tool_name == "read_file":
                result = tools.read_file(args.get("path", ""))
                if result["success"]:
                    return f"📄 파일 내용:\n```\n{result['content'][:1500]}\n```"
                return f"❌ 오류: {result['error']}"

            elif tool_name == "write_file":
                result = tools.write_file(args.get("path", ""), args.get("content", ""))
                if result["success"]:
                    return f"✅ 파일 저장됨: {result['path']}"
                return f"❌ 오류: {result['error']}"

            elif tool_name == "web_search":
                result = tools.web_search(args.get("query", ""))
                if result["success"]:
                    items = result["results"][:3]
                    text = "\n".join([f"• {r['title']}: {r['body'][:100]}..." for r in items])
                    return f"🔍 검색 결과:\n{text}"
                return f"❌ 검색 실패: {result['error']}"

            elif tool_name == "fetch_url":
                result = tools.fetch_url(args.get("url", ""))
                if result["success"]:
                    return f"🌐 페이지 내용:\n{result['content'][:1000]}..."
                return f"❌ 오류: {result['error']}"

            elif tool_name == "python":
                result = tools.run_python(args.get("code", ""))
                if result["success"]:
                    return f"🐍 실행 결과:\n```\n{result['output']}\n```"
                return f"❌ 오류: {result['error']}"

            elif tool_name == "system_info":
                info = tools.get_system_info()
                return f"💻 시스템: CPU {info.get('cpu_percent', '?')}%, 메모리 {info.get('memory_percent', '?')}%, 디스크 {info.get('disk_percent', '?')}%"

            elif tool_name == "image":
                url = tools.generate_image(args.get("prompt", ""))
                return f"IMAGE_URL:{url}"

            # 브라우저 도구
            elif tool_name == "browser_open":
                result = tools.browser_open(args.get("url", ""))
                if result["success"]:
                    return f"🌐 브라우저 열림: {result.get('title', '')} ({result.get('url', '')})"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_screenshot":
                result = tools.browser_capture()
                if result["success"]:
                    return f"📸 스크린샷 저장: {result.get('path', '')}\nBROWSER_SCREENSHOT:{result.get('path', '')}"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_read":
                result = tools.browser_read()
                if result["success"]:
                    return f"📄 페이지 내용 ({result.get('title', '')}):\n{result.get('text', '')[:1500]}..."
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_google":
                result = tools.browser_google(args.get("query", ""))
                if result["success"]:
                    items = result.get("results", [])[:5]
                    text = "\n".join([f"• {r['title']}: {r.get('snippet', '')[:80]}..." for r in items])
                    return f"🔍 구글 검색 결과:\n{text}"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_click":
                result = tools.browser_click_element(args.get("selector", ""))
                if result["success"]:
                    return f"👆 클릭 완료: {result.get('url', '')}"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_input":
                result = tools.browser_input(args.get("selector", ""), args.get("text", ""))
                if result["success"]:
                    return f"⌨️ 입력 완료"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_links":
                result = tools.browser_get_links()
                if result["success"]:
                    links = result.get("links", [])[:10]
                    text = "\n".join([f"• {l['text'][:50]}: {l['href']}" for l in links])
                    return f"🔗 페이지 링크:\n{text}"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_scroll":
                result = tools.browser_scroll_page(args.get("direction", "down"))
                if result["success"]:
                    return f"📜 스크롤 완료: {result.get('direction', '')}"
                return f"❌ 오류: {result.get('error', '')}"

            elif tool_name == "browser_close":
                result = tools.browser_quit()
                if result["success"]:
                    return "🔴 브라우저 종료됨"
                return f"❌ 오류: {result.get('error', '')}"

            return f"❌ 알 수 없는 도구: {tool_name}"
        except Exception as e:
            return f"❌ 도구 실행 오류: {str(e)}"

    @staticmethod
    def chat(prompt: str, context: str = "", max_iterations: int = 3) -> tuple[str, List[str]]:
        """Claude와 대화 (도구 사용 포함)"""
        messages = []
        tool_results = []
        current_prompt = prompt

        if context:
            current_prompt = f"{context}\n\n사용자: {prompt}"

        for i in range(max_iterations):
            try:
                # Claude 호출
                cmd = [
                    "claude", "-p", current_prompt,
                    "--model", "sonnet",
                    "--system-prompt", ClaudeAgent.SYSTEM_PROMPT
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env={**os.environ, "LANG": "ko_KR.UTF-8"}
                )

                if result.returncode != 0:
                    return "오류가 발생했어요 😅", tool_results

                response = result.stdout.strip()

                # 도구 호출 확인
                tool_calls = ClaudeAgent.parse_tool_calls(response)

                if not tool_calls:
                    # 도구 호출 없으면 최종 응답
                    # 도구 결과 마커 제거
                    clean_response = re.sub(r'```tool.*?```', '', response, flags=re.DOTALL).strip()
                    return clean_response, tool_results

                # 도구 실행
                tool_outputs = []
                for tc in tool_calls:
                    tool_name = tc.get("tool")
                    args = tc.get("args", {})
                    logger.info(f"도구 실행: {tool_name} with {args}")
                    output = ClaudeAgent.execute_tool(tool_name, args)
                    tool_outputs.append(output)
                    tool_results.append(f"[{tool_name}] {output[:200]}")

                # 도구 결과와 함께 다시 요청
                tool_result_text = "\n".join(tool_outputs)
                current_prompt = f"""이전 요청: {prompt}

도구 실행 결과:
{tool_result_text}

위 결과를 바탕으로 사용자에게 답변해줘. 더 필요한 도구가 있으면 사용해."""

            except subprocess.TimeoutExpired:
                return "응답 시간이 초과됐어요 ⏱️", tool_results
            except Exception as e:
                return f"오류: {str(e)[:100]}", tool_results

        return "최대 반복 횟수 초과", tool_results


agent = ClaudeAgent()


# ═══════════════════════════════════════════════════════════════
# 텔레그램 핸들러
# ═══════════════════════════════════════════════════════════════

def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시작"""
    user = update.effective_user
    user_id = user.id

    if not is_allowed(user_id):
        await update.message.reply_text(f"⛔ 허용되지 않은 사용자입니다.\nID: {user_id}")
        return

    # 메모리에 등록
    mem = memory.get_user(user_id)
    mem["name"] = user.first_name
    memory.save()

    keyboard = [
        [
            InlineKeyboardButton("🔧 도구", callback_data="tools"),
            InlineKeyboardButton("🌐 브라우저", callback_data="browser"),
        ],
        [
            InlineKeyboardButton("📰 뉴스", callback_data="news"),
            InlineKeyboardButton("📈 주식", callback_data="stock"),
        ],
        [
            InlineKeyboardButton("🍽️ 점심", callback_data="lunch"),
            InlineKeyboardButton("🎨 이미지", callback_data="image"),
        ],
        [
            InlineKeyboardButton("🧠 메모리", callback_data="memory"),
            InlineKeyboardButton("💻 시스템", callback_data="system"),
        ],
        [
            InlineKeyboardButton("❓ 도움말", callback_data="help"),
        ]
    ]

    await update.message.reply_text(
        f"안녕하세요 {user.first_name}님! 🤖\n\n"
        f"저는 **AGI 스타일 AI 어시스턴트**예요.\n"
        f"컴퓨터와 브라우저를 직접 제어해요.\n\n"
        f"💬 자연스럽게 대화하세요\n"
        f"🌐 \"google.com 열어줘\"\n"
        f"📁 \"홈 폴더 파일 목록 보여줘\"\n"
        f"🔍 \"파이썬 비동기 검색해줘\"\n"
        f"🐍 \"1부터 10까지 합 계산해줘\"\n"
        f"🎨 \"우주 고양이 그려줘\"\n\n"
        f"뭐든 시켜보세요! 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 콜백"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "tools":
        await query.message.reply_text(
            "🔧 **사용 가능한 도구**\n\n"
            "**시스템**\n"
            "• `shell` - 터미널 명령\n"
            "• `read/write_file` - 파일 읽기/쓰기\n"
            "• `python` - 파이썬 실행\n\n"
            "**브라우저** 🌐\n"
            "• `browser_open` - URL 열기\n"
            "• `browser_google` - 구글 검색\n"
            "• `browser_screenshot` - 스크린샷\n"
            "• `browser_click/input` - 클릭/입력\n\n"
            "**기타**\n"
            "• `web_search` - DuckDuckGo 검색\n"
            "• `image` - 이미지 생성\n\n"
            "자연어로 요청하면 자동으로 도구를 선택해요!",
            parse_mode="Markdown"
        )

    elif data == "browser":
        status = tools.browser_info()
        if status.get("running"):
            await query.message.reply_text(
                f"🌐 **브라우저 상태**\n\n"
                f"✅ 실행 중\n"
                f"📍 현재 URL: {status.get('current_url', 'N/A')}\n"
                f"📜 방문 기록: {status.get('history_count', 0)}개\n\n"
                f"명령어:\n"
                f"• \"google.com 열어\"\n"
                f"• \"스크린샷 찍어\"\n"
                f"• \"페이지 내용 읽어\"",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                "🌐 **브라우저**\n\n"
                "브라우저가 실행되지 않았어요.\n\n"
                "시작하려면:\n"
                "• \"google.com 열어줘\"\n"
                "• \"네이버 열어\"\n"
                "• \"브라우저로 검색해줘 AI 뉴스\"",
                parse_mode="Markdown"
            )

    elif data == "memory":
        user = memory.get_user(user_id)
        facts = user.get("facts", [])
        msg_count = user.get("message_count", 0)
        first_seen = user.get("first_seen", "?")[:10]

        await query.message.reply_text(
            f"🧠 **메모리 상태**\n\n"
            f"📊 대화 수: {msg_count}\n"
            f"📅 처음 만남: {first_seen}\n"
            f"💡 알고 있는 것: {len(facts)}개\n\n"
            f"**학습된 사실:**\n" +
            ("\n".join([f"• {f}" for f in facts[-5:]]) if facts else "아직 없음"),
            parse_mode="Markdown"
        )

    elif data == "system":
        info = tools.get_system_info()
        await query.message.reply_text(
            f"💻 **시스템 상태**\n\n"
            f"🔲 CPU: {info.get('cpu_percent', '?')}%\n"
            f"💾 메모리: {info.get('memory_percent', '?')}%\n"
            f"💿 디스크: {info.get('disk_percent', '?')}%\n"
            f"⏱️ 업타임: {info.get('uptime', '?')}",
            parse_mode="Markdown"
        )

    elif data == "news":
        await query.message.reply_text("📰 뉴스 가져오는 중...")
        await send_content(query.message, "news", user_id)

    elif data == "stock":
        await query.message.reply_text("📈 분석 중...")
        await send_content(query.message, "stock", user_id)

    elif data == "lunch":
        await query.message.reply_text("🍽️ 메뉴 확인 중...")
        await send_content(query.message, "lunch", user_id)

    elif data == "image":
        await query.message.reply_text(
            "🎨 **이미지 생성**\n\n"
            "\"이미지 [설명]\" 또는 \"그려줘 [설명]\"으로 요청하세요!\n\n"
            "예시:\n"
            "• 이미지 우주를 나는 고양이\n"
            "• 그려줘 사이버펑크 도시\n"
            "• image beautiful sunset",
            parse_mode="Markdown"
        )

    elif data == "help":
        await query.message.reply_text(
            "❓ **AGI 봇 가이드**\n\n"
            "이 봇은 실제로 컴퓨터를 제어할 수 있어요!\n\n"
            "**예시 명령:**\n"
            "• \"현재 디렉토리 파일 보여줘\"\n"
            "• \"시스템 메모리 사용량 확인해\"\n"
            "• \"파이썬으로 피보나치 계산해\"\n"
            "• \"최신 AI 뉴스 검색해줘\"\n"
            "• \"오늘 점심 뭐 먹지?\"\n"
            "• \"귀여운 강아지 그려줘\"\n\n"
            "🧠 대화 내용을 기억하고 학습해요!",
            parse_mode="Markdown"
        )


async def send_content(message, content_type: str, user_id: int):
    """컨텐츠 전송"""
    try:
        if content_type == "news":
            import xml.etree.ElementTree as ET
            resp = requests.get("https://news.hada.io/rss/news", timeout=30)
            root = ET.fromstring(resp.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            items = [e.find('atom:title', ns).text for e in root.findall('atom:entry', ns)[:7]]

            response, _ = agent.chat(
                f"다음 뉴스를 간단히 요약해줘:\n" + "\n".join(items),
                ""
            )
            await message.reply_text(f"📰 오늘의 뉴스\n\n{response}")

        elif content_type == "stock":
            import xml.etree.ElementTree as ET
            resp = requests.get("https://news.hada.io/rss/news", timeout=30)
            root = ET.fromstring(resp.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            items = [e.find('atom:title', ns).text for e in root.findall('atom:entry', ns)[:7]]

            response, _ = agent.chat(
                f"이 뉴스가 주식시장에 미칠 영향 분석해줘:\n" + "\n".join(items),
                ""
            )
            await message.reply_text(f"📈 주식 분석\n\n{response}\n\n⚠️ 투자는 본인 책임")

        elif content_type == "lunch":
            import sys
            sys.path.insert(0, '/home/kim/dooray-claude-bot')
            try:
                from lunch_menu import get_all_menus, rank_menus_with_ai
                menus = get_all_menus()
                if menus:
                    clean = {k.split(" 구내식당")[0]: v for k, v in menus.items()}
                    text = "\n".join([f"🍽️ {k}: {v[:100]}" for k, v in clean.items()])
                    ranking = rank_menus_with_ai(clean)
                    await message.reply_text(f"🍴 오늘의 점심\n\n{text}\n\n📊 추천\n{ranking or ''}"[:4000])
                else:
                    await message.reply_text("점심 메뉴를 가져오지 못했어요 😅")
            except Exception as e:
                await message.reply_text(f"메뉴 확인 실패: {str(e)[:100]}")

    except Exception as e:
        await message.reply_text(f"오류: {str(e)[:100]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """메시지 처리 - AGI 스타일"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if not is_allowed(user_id):
        await update.message.reply_text(f"⛔ 허용되지 않은 사용자입니다.\nID: {user_id}")
        return

    text = update.message.text.strip()
    if not text:
        return

    # 메모리에 기록
    memory.add_message(user_id, "user", text)

    # 이미지 생성 직접 처리
    if re.match(r'^(이미지|그려|그림|image|draw)\s+', text, re.I):
        prompt = re.sub(r'^(이미지|그려\s*줘?|그림|image|draw)\s*', '', text, flags=re.I).strip()
        if prompt:
            await update.message.reply_text(f"🎨 그리는 중: {prompt[:50]}...")
            url = tools.generate_image(prompt)
            await update.message.reply_photo(photo=url, caption=f"🖼️ {prompt[:100]}")
            memory.add_message(user_id, "assistant", f"[이미지: {prompt}]")
            return

    # 타이핑 표시
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # 컨텍스트 가져오기
    user_context = memory.get_context(user_id)

    # Claude 에이전트 실행
    await update.message.reply_text("🤔 생각 중...")

    try:
        response, tool_results = agent.chat(text, user_context)

        # 이미지 URL이 있으면 이미지로 전송
        if "IMAGE_URL:" in response:
            match = re.search(r'IMAGE_URL:(https://[^\s]+)', response)
            if match:
                url = match.group(1)
                response = re.sub(r'IMAGE_URL:https://[^\s]+', '', response).strip()
                await update.message.reply_photo(photo=url)

        # 응답이 너무 길면 자르기
        if len(response) > 4000:
            response = response[:4000] + "\n\n...(생략)"

        await update.message.reply_text(response)

        # 도구 사용 기록
        if tool_results:
            for tr in tool_results:
                logger.info(f"Tool result: {tr[:100]}")

        # 메모리에 기록
        memory.add_message(user_id, "assistant", response[:500])

        # 사실 학습 시도 (간단한 패턴)
        if "내 이름은" in text or "나는" in text:
            fact = text[:100]
            memory.learn_fact(user_id, fact)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"오류가 발생했어요: {str(e)[:100]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """이미지 분석"""
    if not is_allowed(update.effective_user.id):
        return

    await update.message.reply_text("🖼️ 이미지를 받았어요! (분석 기능 준비 중)")


async def browser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/browser 명령"""
    if not is_allowed(update.effective_user.id):
        return

    args = context.args
    if not args:
        status = tools.browser_info()
        if status.get("running"):
            await update.message.reply_text(
                f"🌐 브라우저 실행 중\n"
                f"📍 {status.get('current_url', 'N/A')}\n\n"
                f"사용법: /browser [URL]"
            )
        else:
            await update.message.reply_text(
                "🌐 브라우저 사용법:\n"
                "/browser google.com\n"
                "/browser https://naver.com"
            )
        return

    url = args[0]
    await update.message.reply_text(f"🌐 {url} 열는 중...")

    result = tools.browser_open(url)
    if result["success"]:
        # 스크린샷도 찍기
        ss = tools.browser_capture()
        if ss["success"]:
            await update.message.reply_photo(
                photo=open(ss["path"], "rb"),
                caption=f"✅ {result.get('title', '')}\n{result.get('url', '')}"
            )
        else:
            await update.message.reply_text(f"✅ 열림: {result.get('title', '')}")
    else:
        await update.message.reply_text(f"❌ 오류: {result.get('error', '')}")


async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/screenshot 명령"""
    if not is_allowed(update.effective_user.id):
        return

    status = tools.browser_info()
    if not status.get("running"):
        await update.message.reply_text("🌐 브라우저가 실행 중이 아니에요.\n/browser [URL]로 먼저 열어주세요.")
        return

    await update.message.reply_text("📸 스크린샷 촬영 중...")

    result = tools.browser_capture()
    if result["success"]:
        await update.message.reply_photo(
            photo=open(result["path"], "rb"),
            caption=f"📸 {status.get('current_url', '')}"
        )
    else:
        await update.message.reply_text(f"❌ 오류: {result.get('error', '')}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search 명령"""
    if not is_allowed(update.effective_user.id):
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("🔍 검색어를 입력해주세요.\n예: /search AI 뉴스")
        return

    await update.message.reply_text(f"🔍 '{query}' 검색 중...")

    result = tools.browser_google(query)
    if result["success"]:
        items = result.get("results", [])[:5]
        text = "\n\n".join([f"• **{r['title']}**\n{r.get('snippet', '')[:100]}" for r in items])
        await update.message.reply_text(f"🔍 검색 결과:\n\n{text}", parse_mode="Markdown")

        # 스크린샷도
        ss = tools.browser_capture()
        if ss["success"]:
            await update.message.reply_photo(photo=open(ss["path"], "rb"))
    else:
        await update.message.reply_text(f"❌ 검색 실패: {result.get('error', '')}")


def main():
    """봇 시작"""
    print("🤖 AGI 텔레그램 봇 시작...")
    print(f"📂 데이터 디렉토리: {DATA_DIR}")

    request = HTTPXRequest(connect_timeout=30.0, read_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    # 핸들러
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("browser", browser_command))
    app.add_handler(CommandHandler("screenshot", screenshot_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("✅ 봇 실행 중! Ctrl+C로 종료")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=5)


if __name__ == "__main__":
    main()
