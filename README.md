# SBS Watch

In-house brand monitoring and AI-visibility tracking, built with Claude Code.

**Team site:** https://cheomolina.github.io/sbs-watch/

## What's here

| Path | What it is |
|---|---|
| `docs/` | The team site, published with GitHub Pages |
| `docs/feasibility.html` | Feasibility map: which social-listening features we can build ourselves, which are worth it, and which aren't possible |
| `docs/news.html` | News monitor dashboard: share of voice, daily trend, top publishers and headlines |
| `docs/data/news.json` | Collected headlines (headline, publisher, date, link only), updated daily |
| `docs/assets/` | Downloads, including the PDF version of the feasibility map |
| `collector/` | The news collector script and `brands.json`, which sets the brands, search queries and relevance rules |
| `.github/workflows/collect-news.yml` | Runs the collector every day at 05:17 UTC and commits the new data |

## News collector

The collector searches Google News (English, French and German) for each brand, keeps headlines that name the brand, drops stock-ticker and share-disclosure filler, and merges the results into `docs/data/news.json`. It uses only the Python standard library, so there's nothing to install.

- **Run it locally:** `python collector/collect_news.py`
- **Run it on GitHub:** Actions tab → "Collect news" → "Run workflow"
- **Track a new brand or fix noisy results:** edit `collector/brands.json`. Each brand has search `queries`, a `match` regex the headline must contain, and an optional `exclude` regex. There's also a global `exclude` for noise. The rules are re-applied to stored headlines on every run, so tightening them cleans old data too.

## Roadmap

- [x] **Phase 0: feasibility and workspace.** Feasibility map, team site and repository.
- [ ] **Phase 1: AI visibility tracker.** Scheduled buyer prompts against ChatGPT, Perplexity, Gemini and Claude. Tracks mentions, rank, share of voice and cited sources against competitors.
- [ ] **Phase 2: focused listening.** *Started: daily news monitoring is live.* Next: blogs, Reddit, YouTube, Hacker News and reviews, with AI sentiment, intent and topics, a weekly briefing and alerts. Needs a GDPR review and a private dashboard first.
- [ ] **Phase 3: closed platforms.** Instagram, Facebook, TikTok and LinkedIn can't be built in-house. Decide whether to buy a vendor.

## How we work

1. Every task starts as a GitHub issue.
2. Work on a branch and open a pull request. One teammate reviews before merging into `main`.
3. Anything merged into `docs/` on `main` is published to the team site automatically.

## Ground rules: this repository is public

- **No secrets.** API keys and tokens go in GitHub Actions secrets or a local `.env` file (already git-ignored), never in commits.
- **No personal data.** No collected posts, author names or raw mentions. Only code and aggregated results.
- **No confidential material.** No customer names, internal figures or anything you wouldn't post publicly.
