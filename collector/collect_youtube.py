"""Collect YouTube videos that mention our brand and competitors.

Reads the "youtube" section of collector/brands.json, searches the YouTube Data
API for every brand and language, keeps videos whose title or description names
the brand, refreshes view counts for stored videos, and writes
docs/data/youtube.json, which the dashboard reads. Standard library only.

Needs a YouTube Data API key in the YOUTUBE_API_KEY environment variable (a
GitHub Actions secret, or a line YOUTUBE_API_KEY=... in a local .env file).
Without one it exits quietly, so the rest of the daily workflow still runs.

Stored per video: title, channel, date, language, views, likes, comments, link.
No comments' text and no commenters.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "collector" / "brands.json"
OUTPUT = ROOT / "docs" / "data" / "youtube.json"
API = "https://www.googleapis.com/youtube/v3/"


def api_key():
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("YOUTUBE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key


def call(endpoint, key, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode({**params, "key": key})
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        # Never echo the URL: it contains the key
        detail = json.loads(error.read() or b"{}").get("error", {}).get("message", "")
        raise RuntimeError(f"YouTube API {endpoint} returned {error.code}: {detail}") from None


def relevance_rules(config):
    global_exclude = re.compile(config["exclude"], re.IGNORECASE) if config.get("exclude") else None
    rules = {}
    for name, brand in config["youtube"]["brands"].items():
        match = re.compile(brand["match"], re.IGNORECASE)
        exclude = re.compile(brand["exclude"], re.IGNORECASE) if brand.get("exclude") else None

        def test(text, match=match, exclude=exclude):
            if not match.search(text):
                return False
            if exclude and exclude.search(text):
                return False
            return not (global_exclude and global_exclude.search(text))

        rules[name] = test
    return rules


def video_language(snippet, fallback):
    lang = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").lower()
    return lang[:2] if lang else fallback


def main():
    key = api_key()
    if not key:
        print("No YOUTUBE_API_KEY set; skipping YouTube collection")
        return

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    settings = config["youtube"]
    rules = relevance_rules(config)
    languages = settings["languages"]
    since = (datetime.now(timezone.utc) - timedelta(days=settings["lookback_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")

    stored = {}
    if OUTPUT.exists():
        stored = {v["id"]: v for v in json.loads(OUTPUT.read_text(encoding="utf-8"))["videos"]}

    # 1. Search: 100 quota units per call
    candidates, units = {}, 0
    for name, brand in settings["brands"].items():
        for lang in languages:
            for query in brand["queries"]:
                result = call("search", key, part="snippet", q=query, type="video", order="date",
                              publishedAfter=since, relevanceLanguage=lang, maxResults=50)
                units += 100
                for item in result.get("items", []):
                    candidates.setdefault(item["id"]["videoId"], lang)

    # 2. Details and stats for new candidates plus everything stored: 1 unit per 50 videos
    ids = list(dict.fromkeys(list(candidates) + list(stored)))
    details = {}
    for start in range(0, len(ids), 50):
        result = call("videos", key, part="snippet,statistics", id=",".join(ids[start:start + 50]), maxResults=50)
        units += 1
        for item in result.get("items", []):
            details[item["id"]] = item

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    videos, dropped = {}, 0
    for video_id in ids:
        item = details.get(video_id)
        if not item:  # deleted or made private
            continue
        snippet, stats = item["snippet"], item.get("statistics", {})
        text = snippet.get("title", "") + "\n" + snippet.get("description", "")
        brands = [name for name, test in rules.items() if test(text)]
        lang = stored.get(video_id, {}).get("lang") or video_language(snippet, candidates.get(video_id, "en"))
        if not brands or lang not in languages:
            dropped += 1
            continue
        videos[video_id] = {
            "id": video_id,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "published": snippet.get("publishedAt", ""),
            "lang": lang,
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "brands": brands,
            "first_seen": stored.get(video_id, {}).get("first_seen", now),
            "stats_updated": now,
        }

    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings["retention_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    kept = sorted((v for v in videos.values() if v["published"] >= cutoff), key=lambda v: v["published"], reverse=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "updated": now,
        "brands": list(settings["brands"]),
        "videos": kept,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in settings["brands"]:
        print(f"{name}: {sum(name in v['brands'] for v in kept)} videos")
    print(f"Saved {len(kept)} videos ({dropped} off-topic or other-language dropped, {units} API units used)")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        sys.exit(str(error))
