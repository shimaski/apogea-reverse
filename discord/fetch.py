#!/usr/bin/env python3
"""
Fetch read-accessible Discord channels (user token) and store normalized
messages as JSON per channel.

- Backfills the FULL history on first run per channel, then only fetches the
  delta (messages newer than the last stored id) on subsequent runs.
- Output: discord/data/<channel_name>.json  =>  {"messages":[...], "meta":{...}}
- Cache (<channel_name>.cache.json) holds progress (last message id) only, so
  the JSON data file can be loaded straight into a wiki/Lovable.

Schema (per message), matching the requested format:
  message_id, channel_id, channel_name, author{id,username,display_name,avatar},
  content, published_at, edited_at, embeds[], attachments[], source_url
"""
import json
import os
import sys
import time
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API = "https://discord.com/api/v9"
TOKEN_ENV = "DISCORD_TOKEN"
BASE_DIR = Path(__file__).resolve().parent
CHANNELS_FILE = BASE_DIR / "channels.json"
DATA_DIR = BASE_DIR / "data"
PAGE_SIZE = 100


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_url(path, params=None):
    url = API + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return url


def api_get(token, path, params=None, retries=4):
    url = build_url(path, params)
    props = {
        "os": "Windows", "browser": "Chrome", "device": "",
        "system_locale": "pt-BR", "browser_user_agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "browser_version": "151.0.0.0", "os_version": "10",
        "referrer": "", "referring_domain": "", "search_engine": "",
        "release_channel": "stable", "client_build_number": 589596,
        "client_event_source": None,
    }
    xprops = base64.b64encode(
        json.dumps(props, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    req = urllib.request.Request(url, method="GET", headers={
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "x-super-properties": xprops,
        "x-discord-locale": "pt-BR",
        "x-debug-options": "bugReporterEnabled",
        "Sec-Fetch-User": "?1",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = 1.0
                try:
                    retry = float(json.loads(e.read().decode("utf-8")).get("retry_after", 1))
                except Exception:
                    pass
                time.sleep(retry + 0.5)
                continue
            if e.code == 403:
                print(f"  403 (sem acesso): {path}", file=sys.stderr)
                return None
            if e.code == 404:
                print(f"  404: {path}", file=sys.stderr)
                return None
            if e.code == 401:
                print("  401 not authorized - token invalido", file=sys.stderr)
                return None
            # generic: backoff on server/5xx
            if e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError as e:
            time.sleep(2 ** attempt)
            continue
    return None


def channel_info(token, cid):
    return api_get(token, f"/channels/{cid}")


def fetch_page_messages(token, cid, before=None, after=None):
    params = {"limit": str(PAGE_SIZE)}
    if before:
        params["before"] = str(before)
    if after:
        params["after"] = str(after)
    return api_get(token, f"/channels/{cid}/messages", params) or []


def fetch_all_history(token, cid, max_pages=50):
    """History oldest->newest, capped at max_pages (100 msgs each).
    Default 5000 messages per channel; channel.json can override with "max_pages"."""
    pages = []
    before = None
    for _ in range(max_pages):
        page = fetch_page_messages(token, cid, before=before)
        if not page:
            break
        pages.extend(page)
        if len(page) < PAGE_SIZE:
            break
        before = page[-1]["id"]
    return list(reversed(pages))


def fetch_new_since(token, cid, since_id):
    out = []
    after = since_id
    while True:
        page = fetch_page_messages(token, cid, after=after)
        if not page:
            break
        out.extend(page)
        if len(page) < PAGE_SIZE:
            break
        after = page[-1]["id"]
    return out


def load_channels():
    data = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    return data.get("channels", [])


def load_store(channel_name):
    p = DATA_DIR / f"{channel_name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def write_store(channel_name, payload):
    p = DATA_DIR / f"{channel_name}.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def normalize(channel, msg, guild_id=None):
    author = msg.get("author") or {}
    av = author.get("avatar")
    src = f"https://discord.com/channels/{channel['id']}/{msg.get('id')}"
    if guild_id:
        src = f"https://discord.com/channels/{guild_id}/{channel['id']}/{msg.get('id')}"
    return {
        "message_id": msg.get("id"),
        "channel_id": channel["id"],
        "channel_name": channel["name"],
        "author": {
            "id": author.get("id"),
            "username": author.get("username"),
            "display_name": author.get("global_name") or author.get("username"),
            "avatar": f"https://cdn.discordapp.com/avatars/{author['id']}/{av}.png?size=128"
                      if av else None,
        },
        "content": msg.get("content") or "",
        "published_at": msg.get("timestamp"),
        "edited_at": msg.get("edited_timestamp"),
        "embeds": [
            {
                "type": e.get("type"),
                "title": e.get("title"),
                "description": e.get("description"),
                "url": e.get("url"),
                "color": e.get("color"),
                "author_name": (e.get("author") or {}).get("name"),
                "thumbnail": (e.get("thumbnail") or {}).get("url"),
                "image": (e.get("image") or {}).get("url"),
            }
            for e in (msg.get("embeds") or [])
        ],
        "attachments": [
            {
                "id": a.get("id"),
                "url": a.get("url"),
                "filename": a.get("filename"),
                "content_type": a.get("content_type"),
                "size": a.get("size"),
                "width": a.get("width"),
                "height": a.get("height"),
            }
            for a in (msg.get("attachments") or [])
        ],
        "source_url": src,
    }


def main():
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print("DISCORD_TOKEN env var is required", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    channels = load_channels()
    if not channels:
        print("no channels configured", file=sys.stderr)
        return 2

    results = {}
    for ch in channels:
        cid, cname = ch["id"], ch["name"]
        print(f"[{cname}] reading channel {cid} ...", flush=True)

        info = channel_info(token, cid)
        if not info:
            print(f"[{cname}] SKIP (not accessible)", flush=True)
            results[cname] = {"status": "skip", "count": 0}
            continue
        guild_id = info.get("guild_id")

        store = load_store(cname) or {}
        existing = store.get("messages") or []
        msgs_by_id = {m["message_id"]: m for m in existing}

        if existing:
            last_id = max(int(mid) for mid in msgs_by_id)
            fetched = fetch_new_since(token, cid, str(last_id))
        else:
            fetched = fetch_all_history(token, cid, ch.get("max_pages", 50))

        added = 0
        for m in fetched:
            n = normalize(ch, m, guild_id)
            if n["message_id"] in msgs_by_id:
                continue
            msgs_by_id[n["message_id"]] = n
            added += 1

        if fetched or not existing:
            ordered = sorted(msgs_by_id.values(), key=lambda m: int(m["message_id"]))
            write_store(cname, {
                "meta": {"channel_id": cid, "channel_name": cname,
                         "guild_id": guild_id, "updated": now_iso(),
                         "total": len(ordered)},
                "messages": ordered,
            })

        results[cname] = {"status": "ok", "added": added,
                          "total": len(msgs_by_id), "first_fetch": not bool(existing)}
        print(f"[{cname}] added={added} total={len(msgs_by_id)}", flush=True)

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())