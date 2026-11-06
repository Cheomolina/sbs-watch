"""Collect YouTube videos that mention our brand and competitors.

Reads the "youtube" section of collector/brands.json, takes every recent upload
from each brand's official channel, searches the YouTube Data API for
third-party videos whose title or description names the brand in a banking
context, refreshes view counts for stored videos, and writes
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
    """Return {brand: test(text) -> bool} for third-party videos."""
    settings = config["youtube"]
    excludes = [re.compile(p, re.IGNORECASE) for p in (config.get("exclude"), settings.get("exclude")) if p]
    context = re.compile(settings["context"], re.IGNORECASE) if settings.get("context") else None
    rules = {}
    for name, brand in settings["brands"].items():
        match = re.compile(brand["match"], re.IGNORECASE)
        exclude = re.compile(brand["exclude"], re.IGNORECASE) if brand.get("exclude") else None

        def test(text, match=match, exclude=exclude):
            if not match.search(text) or (context and not context.search(text)):
                return False
            if exclude and exclude.search(text):
                return False
            return not any(pattern.search(text) for pattern in excludes)

        rules[name] = test
    return rules


STOPWORDS = {
    "en": {"the", "and", "for", "with", "how", "why", "of", "to", "is", "in", "on", "your", "our", "what", "from", "are"},
    "fr": {"le", "les", "des", "une", "pour", "avec", "et", "du", "est", "dans", "sur", "au", "aux", "nous", "vous", "comment", "pourquoi"},
    # Spanish is detected only so it can be dropped
    "es": {"el", "los", "las", "con", "del", "para", "por", "que", "y", "una", "cómo", "qué", "pagos", "instantáneos"},
}


def video_language(snippet, fallback):
    """Detect the language from the words used; channel language settings are often wrong."""
    words = re.findall(r"[a-zà-ÿ]+", (snippet.get("title", "") + " " + snippet.get("description", "")[:400]).lower())
    scores = sorted(((sum(w in vocab for w in words), lang) for lang, vocab in STOPWORDS.items()), reverse=True)
    if scores[0][0] > scores[1][0]:
        return scores[0][1]
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

    # 2. Official channels: every recent upload counts for its brand, 1 unit per call
    official = {}
    for name, brand in settings["brands"].items():
        if not brand.get("channel_id"):
            continue
        uploads = "UU" + brand["channel_id"][2:]
        result = call("playlistItems", key, part="snippet", playlistId=uploads, maxResults=50)
        units += 1
        for item in result.get("items", []):
            if item["snippet"].get("publishedAt", "") >= since:
                video_id = item["snippet"]["resourceId"]["videoId"]
                official[video_id] = name
                candidates.setdefault(video_id, "en")
    official_channels = {b["channel_id"]: name for name, b in settings["brands"].items() if b.get("channel_id")}

    # 3. Details and stats for new candidates plus everything stored: 1 unit per 50 videos
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
        owner = official.get(video_id) or official_channels.get(snippet.get("channelId", ""))
        brands = [owner] if owner else [name for name, test in rules.items() if test(text)]
        lang = video_language(snippet, candidates.get(video_id) or stored.get(video_id, {}).get("lang", "en"))
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
            "official": bool(owner),
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
