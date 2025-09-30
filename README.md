# Xiaohongshu Keyword Watcher

A lightweight GitHub Actions workflow that keeps an eye on Xiaohongshu (小红书) for new posts matching your keywords and relays them to a Telegram chat. The workflow runs on a schedule, remembers which posts have already been processed, and can be dispatched manually when you want an immediate check.

## How It Works
- Runs hourly by default via `.github/workflows/xhs.yml`; you can tweak the cron expression to suit your needs.
- Installs Python 3.11, the project requirements from `requirements.txt`, and Playwright Chromium so the scraper can run in Actions.
- Executes `xhs_watch.py`, which reads keywords from environment variables, checks each result, and sends new matches (with cover image + summary when available) to Telegram. Only notes published within the last 14 days are forwarded.
- Persists the list of seen post IDs between runs (`xhs_seen.json`) using the Actions artifacts API so duplicates are not re-sent.

## Required Secrets
Create the following repository secrets so the workflow can authenticate and know what to look for:
- `KEYWORDS` – Comma-separated or newline-separated list of search terms.
- `TG_BOT_TOKEN` – Token for your Telegram bot (from @BotFather).
- `TG_CHAT_ID` – Chat or channel ID where notifications should be delivered (include the `-100` prefix for channels/supergroups).
- `XHS_COOKIE` – Required; copy the `name=value; name2=value2` cookie string from a logged-in Xiaohongshu browser session (see instructions below).
- `USER_AGENT` – The exact desktop browser UA used when capturing the cookie (e.g. `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...`).

The workflow also sets `HEADLESS=1` for Playwright by default. Adjust the environment block in `.github/workflows/xhs.yml` if you need to override any values or add custom headers.

### Capturing `XHS_COOKIE` and `USER_AGENT`
1. Open https://www.xiaohongshu.com/ in a normal browser window and sign in.
2. Open Developer Tools → Network tab (enable “Preserve log”).
3. Visit a search page such as `https://www.xiaohongshu.com/search_result?keyword=...` and wait for it to load.
4. In the request list, locate a successful call whose URL contains `sns/web/v1/search/notes`.
5. Copy the entire `Cookie` header from the Request Headers section and store it as the `XHS_COOKIE` secret.
6. Copy the `User-Agent` header from the same request (or from DevTools → Network → top right context menu) and store it as the `USER_AGENT` secret.
7. Cookies expire frequently; repeat this process when the workflow starts returning 400 responses from the Xiaohongshu API.

## Running Locally
You can execute the watcher script on your machine before pushing changes:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\Scripts\activate
pip install -r requirements.txt

export KEYWORDS="term1, term2"
export TG_BOT_TOKEN="123456:ABC"
export TG_CHAT_ID="-100987654321"
export XHS_COOKIE="name=value; other=123"
export USER_AGENT="Mozilla/5.0 ..."
python xhs_watch.py
```

The script stores seen post IDs in `xhs_seen.json`. Delete that file if you want to re-send previously discovered posts during local testing.

## Customisation Tips
- Update the schedule or add additional triggers in `.github/workflows/xhs.yml` for finer control.
- Extend `xhs_watch.py` with richer filtering (e.g., author names, tags) before sending messages to Telegram.
- Tune `max_posts_per_keyword` or scrolling logic in `search_posts` if you want a deeper result set.
- If no posts appear, check the workflow logs: 400 responses from `sns/web/v1/search/notes` usually mean the cookie expired or the UA/header set does not match the captured session.
- Telegram posts include the note title, a short summary, and the cover image when Xiaohongshu returns one; tweak `build_post_message` if you want a different caption format.
- By default only notes published in the last 14 days are sent. Adjust `MAX_POST_AGE` in `xhs_watch.py` if you want a different retention window.

Push changes to GitHub and the workflow will monitor Xiaohongshu automatically on the configured schedule.
