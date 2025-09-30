import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Set

import requests
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from requests import HTTPError


SEEN_FILE = Path("xhs_seen.json")


def load_keywords() -> List[str]:
    raw = os.getenv("KEYWORDS", "").strip()
    if not raw:
        return []
    # Allow comma or newline separated
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def load_seen() -> Set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: Set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    if not bot_token or not chat_id:
        print("Telegram token or chat id missing; skipping send")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=20)
    try:
        resp.raise_for_status()
    except HTTPError as exc:
        detail = resp.text
        print(f"Telegram API error: status={resp.status_code}, body={detail}", file=sys.stderr)
        raise exc

    print(f"Telegram message sent to {chat_id}: {text.splitlines()[0] if text else '<empty>'}")


def parse_cookie_string(raw_cookie: str) -> List[dict]:
    cookies: List[dict] = []
    for part in raw_cookie.split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        name, value = part.split('=', 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        cookies.append({
            'name': name,
            'value': value,
            'domain': '.xiaohongshu.com',
            'path': '/',
            'httpOnly': False,
            'secure': True,
            'sameSite': 'Lax',
        })
    return cookies


def search_posts(keywords: List[str], *, cookie: Optional[str] = None, headless: bool = True, max_posts_per_keyword: int = 20) -> List[dict]:
    results: List[dict] = []
    seen_ids: Set[str] = set()
    cookie = (cookie or '').strip()
    user_agent = os.getenv(
        'USER_AGENT',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1280, 'height': 720},
        )
        try:
            if cookie:
                parsed = parse_cookie_string(cookie)
                if parsed:
                    context.add_cookies(parsed)

            base_url = 'https://www.xiaohongshu.com'
            for keyword in keywords:
                page = context.new_page()
                try:
                    print(f"Fetching keyword '{keyword}'")
                    encoded_keyword = urllib.parse.quote(keyword)
                    search_url = f"{base_url}/search/result?keyword={encoded_keyword}"
                    page.goto(search_url, wait_until='networkidle', timeout=45000)
                    try:
                        page.wait_for_selector("a[href^='/explore/']", timeout=20000)
                    except PlaywrightTimeoutError:
                        pass

                    anchors = page.eval_on_selector_all(
                        "a[href^='/explore/']",
                        """(elements) => elements.map((el) => ({
                            href: el.getAttribute('href'),
                            title: (el.innerText || '').trim()
                        }))""",
                    )
                    print(f"Found {len(anchors)} anchors for keyword '{keyword}'")

                    count_for_keyword = 0
                    for entry in anchors:
                        href = entry.get('href')
                        title = entry.get('title')
                        if not href or not href.startswith('/explore/'):
                            continue
                        post_id = href.split('/')[-1].split('?')[0]
                        if not post_id or post_id in seen_ids:
                            continue
                        title = title or f"XHS post {post_id}"
                        results.append({
                            'id': post_id,
                            'title': title,
                            'url': f"{base_url}{href}",
                        })
                        seen_ids.add(post_id)
                        count_for_keyword += 1
                        print(f"Queued post {post_id} for keyword '{keyword}'")
                        if count_for_keyword >= max_posts_per_keyword:
                            break
                except PlaywrightTimeoutError:
                    print(f"Timed out while fetching results for keyword: {keyword}", file=sys.stderr)
                except Exception as exc:
                    print(f"Failed to fetch keyword '{keyword}': {exc}", file=sys.stderr)
                finally:
                    page.close()
        finally:
            context.close()
            browser.close()

    return results


def main() -> int:
    keywords = load_keywords()
    if not keywords:
        print("No KEYWORDS provided; exiting.")
        # still ensure the seen file exists to satisfy artifact step
        save_seen(set())
        return 0

    print(f"Loaded keywords: {keywords}")

    tg_token = os.getenv("TG_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TG_CHAT_ID", "").strip()
    if not tg_token:
        print("TG_BOT_TOKEN is empty")
    if not tg_chat_id:
        print("TG_CHAT_ID is empty")

    seen = load_seen()
    new_seen = set(seen)
    print(f"Loaded seen ids: {len(seen)}")

    headless_env = os.getenv('HEADLESS', '1').strip().lower()
    headless = headless_env not in {'0', 'false', 'no'}
    xhs_cookie = os.getenv('XHS_COOKIE', '')
    print(f"Headless mode: {headless}; cookie provided: {'yes' if xhs_cookie else 'no'}")

    posts = search_posts(
        keywords,
        cookie=xhs_cookie,
        headless=headless,
    )
    print(f"Total posts fetched: {len(posts)}")

    # If first run (no seen), only send up to 10 recent posts
    is_first_run = len(seen) == 0
    if is_first_run:
        posts = posts[:10]
        print(f"First run detected; truncated posts to {len(posts)}")

    for post in posts:
        pid = post["id"]
        if pid in seen:
            continue
        message = f"{post['title']}\n{post['url']}"
        print(f"Attempting to send post {pid}: {post['url']}")
        try:
            send_telegram_message(tg_token, tg_chat_id, message)
            new_seen.add(pid)
        except Exception as e:
            print(f"Failed to send TG message for {pid}: {e}", file=sys.stderr)

    save_seen(new_seen)
    return 0


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main()
    except Exception as e:
        print(f"Unhandled error: {e}", file=sys.stderr)
        try:
            if not SEEN_FILE.exists():
                save_seen(set())
        except Exception:
            pass
        exit_code = 0
    else:
        try:
            if not SEEN_FILE.exists():
                save_seen(set())
        except Exception:
            pass
    raise SystemExit(exit_code)
