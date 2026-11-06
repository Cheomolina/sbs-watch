# SBS Watch

In-house brand monitoring and AI-visibility tracking, built with Claude Code.

**Team site:** https://sbs-dm.github.io/sbs-watch/

## What's here

| Path | What it is |
|---|---|
| `docs/` | The team site, published with GitHub Pages |
| `docs/feasibility.html` | Feasibility map: which social-listening features we can build ourselves, which are worth it, and which aren't possible |
| `docs/news.html` | Google News Monitor dashboard: share of voice, daily trend, top publishers and headlines |
| `docs/youtube.html` | YouTube Monitor dashboard: videos and views per brand, share of voice, weekly trend, top channels and videos |
| `docs/data/news.json` | Collected headlines (headline, publisher, date, link only), updated daily |
| `docs/data/youtube.json` | Collected videos (title, channel, date, link, view/like/comment counts), updated daily |
| `docs/assets/` | Downloads, including the PDF version of the feasibility map |
| `collector/` | The Google News and YouTube collector scripts, and `brands.json`, which sets the brands, search queries and relevance rules |
| `.github/workflows/collect-news.yml` | The "Collect data" workflow: runs both collectors every day at 05:17 UTC and commits the new data |

## Collectors

### Google News

The collector searches Google News (English and French) for each brand, keeps headlines that name the brand, drops stock-ticker and share-disclosure filler, and merges the results into `docs/data/news.json`. It uses only the Python standard library, so there's nothing to install.

- **Run it locally:** `python collector/collect_news.py`
- **Run it on GitHub:** Actions tab → "Collect data" → "Run workflow"
- **Track a new brand or fix noisy results:** edit `collector/brands.json`. Each brand has search `queries`, a `match` regex the headline must contain, and an optional `exclude` regex. There's also a global `exclude` for noise. The rules are re-applied to stored headlines on every run, so tightening them cleans old data too.
- **Regions:** each headline is tagged with the countries and regions it names (for example "Rawbank … in the DRC" → DR Congo, Middle East & Africa), using the place-name rules in `collector/regions.json`. Headlines that name no place are "Not specified". Google News country editions return nearly the same global articles, so the edition isn't a usable signal for geography.
- **Download report:** the button on the dashboard prints exactly what's on screen, with the active filters listed at the top. Choose "Save as PDF" in the print dialog to get a file.

### YouTube

`collector/collect_youtube.py` searches YouTube (English and French) for each brand through the YouTube Data API, keeps videos whose title or description names the brand, and refreshes view, like and comment counts for every stored video on each run. Settings are in the `youtube` section of `brands.json`.

- **API key:** a free YouTube Data API v3 key, stored as the Actions secret `YOUTUBE_API_KEY`. To run locally, put `YOUTUBE_API_KEY=...` in a `.env` file at the repo root (git-ignored). Without a key the collector skips quietly.
- **Quota:** each search costs 100 of the 10,000 free daily units. The current settings use about 1,400 a day.

## Roadmap

- [x] **Phase 0: feasibility and workspace.** Feasibility map, team site and repository.
- [ ] **Phase 1: AI visibility tracker.** Scheduled buyer prompts against ChatGPT, Perplexity, Gemini and Claude. Tracks mentions, rank, share of voice and cited sources against competitors.
- [ ] **Phase 2: focused listening.** *Started: the Google News Monitor and YouTube Monitor are live.* Next: blogs, Reddit, Hacker News and reviews, with AI sentiment, intent and topics, a weekly briefing and alerts. Needs a GDPR review and a private dashboard first.
- [ ] **Phase 3: closed platforms.** Instagram, Facebook, TikTok and LinkedIn can't be built in-house. Decide whether to buy a vendor.

## How we work

1. Every task starts as a GitHub issue.
2. Work on a branch and open a pull request. One teammate reviews before merging into `main`.
3. Anything merged into `docs/` on `main` is published to the team site automatically.

## Ground rules: this repository is public

- **No secrets.** API keys and tokens go in GitHub Actions secrets or a local `.env` file (already git-ignored), never in commits.
- **No personal data.** We store only what publishers make public about their own content: headline or video title, publisher or channel name, date, link and public counts. No comments, commenters, article text or posts by private individuals.
- **No confidential material.** No customer names, internal figures or anything you wouldn't post publicly.
