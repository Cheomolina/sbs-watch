"""Collect news headlines that mention our brand and competitors.

Reads collector/brands.json, queries Google News RSS for every brand, query and
language edition, keeps headlines that name the brand, and merges them into
docs/data/news.json, which the dashboard reads. Standard library only.

Only headline, publisher, date and link are stored: no article text, no authors.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "collector" / "brands.json"
OUTPUT = ROOT / "docs" / "data" / "news.json"
USER_AGENT = "Mozilla/5.0 (compatible; sbs-watch news collector)"


def fetch_feed(query, edition, lookback):
    params = {"q": f"{query} when:{lookback}", "hl": edition["hl"], "gl": edition["gl"], "ceid": edition["ceid"]}
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return ET.fromstring(response.read())
        except Exception as error:
            if attempt == 2:
                raise
            print(f"  retrying after error: {error}")
            time.sleep(5 * (attempt + 1))


def parse_items(root, lang):
    for item in root.iter("item"):
        source = item.find("source")
        publisher = source.text.strip() if source is not None and source.text else ""
        title = item.findtext("title", "").strip()
        # Google News appends " - Publisher" to every headline
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].strip()
        published = parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc)
        yield {
            "id": item.findtext("guid", "") or item.findtext("link", ""),
            "title": title,
            "source": publisher,
            "published": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lang": lang,
            "url": item.findtext("link", ""),
        }


def relevance_rules(config):
    """Return {brand: test(title) -> bool} built from the match/exclude regexes."""
    global_exclude = re.compile(config["exclude"], re.IGNORECASE) if config.get("exclude") else None
    rules = {}
    for brand in config["brands"]:
        match = re.compile(brand["match"], re.IGNORECASE)
        exclude = re.compile(brand["exclude"], re.IGNORECASE) if brand.get("exclude") else None

        def test(title, match=match, exclude=exclude):
            if not match.search(title):
                return False
            if exclude and exclude.search(title):
                return False
            return not (global_exclude and global_exclude.search(title))

        rules[brand["name"]] = test
    return rules


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rules = relevance_rules(config)
    existing = {}
    if OUTPUT.exists():
        existing = {a["id"]: a for a in json.loads(OUTPUT.read_text(encoding="utf-8"))["articles"]}

    found, errors, dropped = {}, 0, 0
    for brand in config["brands"]:
        is_relevant = rules[brand["name"]]
        kept = 0
        for edition in config["editions"]:
            for query in brand["queries"]:
                try:
                    root = fetch_feed(query, edition, config["lookback"])
                except Exception as error:
                    errors += 1
                    print(f"[{brand['name']}/{edition['lang']}] failed for {query!r}: {error}")
                    continue
                for article in parse_items(root, edition["lang"]):
                    if not is_relevant(article["title"]):
                        dropped += 1
                        continue
                    entry = found.setdefault(article["id"], {**article, "brands": []})
                    if brand["name"] not in entry["brands"]:
                        entry["brands"].append(brand["name"])
                        kept += 1
                time.sleep(1)
        print(f"{brand['name']}: {kept} relevant headlines")

    # New results win, but keep the first time we saw each article
    for article_id, article in found.items():
        if article_id in existing:
            article["first_seen"] = existing[article_id].get("first_seen", article["published"])
        else:
            article["first_seen"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        existing[article_id] = article

    # Re-apply the current rules and languages to everything stored, so config changes clean old data too
    for article in existing.values():
        article["brands"] = [b for b in article["brands"] if b in rules and rules[b](article["title"])]

    cutoff = (datetime.now(timezone.utc) - timedelta(days=config["retention_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    languages = {e["lang"] for e in config["editions"]}
    articles = sorted((a for a in existing.values() if a["brands"] and a["lang"] in languages and a["published"] >= cutoff),
                      key=lambda a: a["published"], reverse=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brands": [b["name"] for b in config["brands"]],
        "articles": articles,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(articles)} articles ({dropped} off-topic headlines dropped, {errors} failed requests)")

    total_requests = sum(len(b["queries"]) for b in config["brands"]) * len(config["editions"])
    if errors == total_requests:
        sys.exit("Every request failed; nothing collected")


if __name__ == "__main__":
    main()
