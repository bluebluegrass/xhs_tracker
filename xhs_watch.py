import json
import os
import sys
from pathlib import Path
from typing import List, Set

import requests


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
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()


def fake_search_posts(keywords: List[str]) -> List[dict]:
    # Placeholder: replace with real Xiaohongshu scraping via Playwright later
    demo = []
    for kw in keywords:
        demo.append({
            "id": f"demo-{kw}",
            "title": f"Demo result for {kw}",
            "url": f"https://www.xiaohongshu.com/search/result?keyword={kw}",
        })
    return demo


def main() -> int:
    keywords = load_keywords()
    if not keywords:
        print("No KEYWORDS provided; exiting.")
        # still ensure the seen file exists to satisfy artifact step
        save_seen(set())
        return 0

    tg_token = os.getenv("TG_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TG_CHAT_ID", "").strip()

    seen = load_seen()
    new_seen = set(seen)

    # TODO: replace with real search using Playwright and XHS_COOKIE if needed
    posts = fake_search_posts(keywords)

    for post in posts:
        pid = post["id"]
        if pid in seen:
            continue
        message = f"{post['title']}\n{post['url']}"
        try:
            send_telegram_message(tg_token, tg_chat_id, message)
            new_seen.add(pid)
        except Exception as e:
            print(f"Failed to send TG message for {pid}: {e}", file=sys.stderr)

    save_seen(new_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


