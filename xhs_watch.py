import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Set

import requests
import urllib.parse
import textwrap
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from requests import HTTPError


SEEN_FILE = Path("xhs_seen.json")



MAX_POST_AGE = timedelta(days=14)


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


def send_telegram_message(bot_token: str, chat_id: str, text: str, *, photo_url: Optional[str] = None) -> None:
    if not bot_token or not chat_id:
        print("Telegram token or chat id missing; skipping send")
        return

    base_url = f"https://api.telegram.org/bot{bot_token}"
    if photo_url:
        payload = {"chat_id": chat_id, "photo": photo_url, "caption": text}
        resp = requests.post(f"{base_url}/sendPhoto", data=payload, timeout=20)
    else:
        payload = {"chat_id": chat_id, "text": text}
        resp = requests.post(f"{base_url}/sendMessage", json=payload, timeout=20)

    try:
        resp.raise_for_status()
    except HTTPError as exc:
        detail = resp.text
        print(
            f"Telegram API error (photo={bool(photo_url)}): status={resp.status_code}, body={detail}",
            file=sys.stderr,
        )
        raise exc

    action = 'photo' if photo_url else 'message'
    preview = text.splitlines()[0] if text else '<empty>'
    print(f"Telegram {action} sent to {chat_id}: {preview}")


def build_post_message(post: dict) -> str:
    lines = []
    title = (post.get('title') or '').strip()
    if title:
        lines.append(title)
    description = (post.get('description') or '').strip()
    if description:
        compact = ' '.join(description.split())
        snippet = textwrap.shorten(compact, width=220, placeholder='…')
        if snippet:
            lines.append(snippet)
    author = (post.get('author') or '').strip()
    if author:
        lines.append(f"Author: {author}")
    published_at = parse_timestamp(post.get('published_at'))
    if published_at:
        lines.append(published_at.astimezone(timezone.utc).strftime('发布时间（UTC）：%Y-%m-%d %H:%M:%S'))
    url = post.get('url')
    if url:
        lines.append(url)
        lines.append('📲 在 Telegram 手机版打开后，点击链接可跳转至小红书 App 查看完整内容。')
    return '\n'.join(lines)


def parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None

    # Numeric epoch (seconds or milliseconds)
    try:
        value = float(raw)
    except ValueError:
        value = None

    if value is not None:
        if value > 1e12:  # milliseconds
            value /= 1000
        if value > 0:
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except Exception:
                pass

    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except Exception:
        return None


def is_recent_enough(timestamp: datetime) -> bool:
    now = datetime.now(timezone.utc)
    return now - timestamp <= MAX_POST_AGE


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
                    search_params = urllib.parse.urlencode({
                        'keyword': keyword,
                        'source': 'web_search_result_notes',
                    })
                    api_response = None
                    search_url = f"{base_url}/search_result?{search_params}"
                    try:
                        with page.expect_response(
                            lambda resp: (
                                resp.status == 200
                                and 'sns/web/v1/search/notes' in resp.url
                            ),
                            timeout=25000,
                        ) as resp_info:
                            page.goto(search_url, wait_until='networkidle', timeout=45000)
                        api_response = resp_info.value
                        print(
                            f"Captured API response for keyword '{keyword}': {api_response.url}"
                        )
                    except PlaywrightTimeoutError:
                        print(
                            f"Search API response timeout for keyword '{keyword}'",
                            file=sys.stderr,
                        )
                        page.goto(search_url, wait_until='networkidle', timeout=45000)
                    try:
                        page.wait_for_function(
                            "document.querySelectorAll(\"a[href^='/explore/']\").length > 0",
                            timeout=20000,
                        )
                    except PlaywrightTimeoutError:
                        print(
                            f"No explore anchors detected for keyword '{keyword}' within timeout",
                            file=sys.stderr,
                        )
                        page.wait_for_timeout(2000)

                    anchors = page.eval_on_selector_all(
                        "a[href^='/explore/']",
                        """(elements) => elements.map((el) => ({
                            href: el.getAttribute('href'),
                            title: (el.innerText || '').trim()
                        }))""",
                    )
                    print(f"Found {len(anchors)} anchors for keyword '{keyword}'")

                    if api_response is not None:
                        try:
                            payload = api_response.json()
                            items = payload.get('data', {}).get('items', [])
                            print(
                                f"API returned {len(items)} items for keyword '{keyword}'"
                            )
                            for item in items:
                                note_id = item.get('id') or item.get('note_id')
                                note_card = item.get('note_card') or {}
                                title = note_card.get('display_title') or note_card.get('title')
                                note_url = f"{base_url}/explore/{note_id}" if note_id else None
                                if not note_id or note_id in seen_ids or not note_url:
                                    continue
                                published_raw = item.get('time') or note_card.get('time')
                                published_ts = parse_timestamp(published_raw)
                                if published_ts is None:
                                    print(
                                        f"Skipping post {note_id} (invalid timestamp): {published_raw}",
                                        file=sys.stderr,
                                    )
                                    continue
                                if not is_recent_enough(published_ts):
                                    print(
                                        f"Skipping post {note_id} (stale): {published_ts.isoformat()}",
                                        file=sys.stderr,
                                    )
                                    continue
                                results.append({
                                    'id': note_id,
                                    'title': title or f"XHS post {note_id}",
                                    'url': note_url,
                                    'description': (note_card.get('desc') or '').strip(),
                                    'cover_url': (
                                        (note_card.get('cover') or {}).get('url')
                                        or ((note_card.get('image_list') or [{}])[0] or {}).get('url')
                                    ),
                                    'author': ((note_card.get('user') or {}).get('nickname') or ''),
                                    'published_at': published_ts.isoformat(),
                                })
                                seen_ids.add(note_id)
                                print(f"Queued post {note_id} from API for keyword '{keyword}'")
                                if len(results) >= max_posts_per_keyword * len(keywords):
                                    break
                        except Exception as exc:
                            print(
                                f"Failed to parse API payload for keyword '{keyword}': {exc}",
                                file=sys.stderr,
                            )

                    count_for_keyword = 0
                    for entry in anchors:
                        href = entry.get('href')
                        title = entry.get('title')
                        if not href or not href.startswith('/explore/'):
                            continue
                        post_id = href.split('/')[-1].split('?')[0]
                        if not post_id or post_id in seen_ids:
                            continue
                        print(
                            f"Skipping anchor-only post {post_id} – missing timestamp",
                            file=sys.stderr,
                        )
                        count_for_keyword += 1
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

    sent_any = False
    for post in posts:
        pid = post["id"]
        if pid in seen:
            continue
        message = build_post_message(post)
        photo_url = post.get('cover_url')
        print(f"Attempting to send post {pid}: {post['url']}")
        try:
            send_telegram_message(tg_token, tg_chat_id, message, photo_url=photo_url)
        except Exception as e:
            if photo_url:
                print(
                    f"Photo send failed for {pid}, retrying without image: {e}",
                    file=sys.stderr,
                )
                try:
                    send_telegram_message(tg_token, tg_chat_id, message, photo_url=None)
                except Exception as inner:
                    print(f"Failed to send TG message for {pid}: {inner}", file=sys.stderr)
                    continue
            else:
                print(f"Failed to send TG message for {pid}: {e}", file=sys.stderr)
                continue
        new_seen.add(pid)
        sent_any = True

    if not sent_any:
        print("No new posts matched criteria; notifying Telegram")
        try:
            send_telegram_message(
                tg_token,
                tg_chat_id,
                "No new Xiaohongshu posts matched your filters in the last run.",
            )
        except Exception as e:
            print(f"Failed to send empty-result notification: {e}", file=sys.stderr)

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
