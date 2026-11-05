# SBS Watch

In-house brand monitoring and AI-visibility tracking, built with Claude Code.

**Team site:** https://cheomolina.github.io/sbs-watch/

## What's here

| Path | What it is |
|---|---|
| `docs/` | The team site, published with GitHub Pages |
| `docs/feasibility.html` | Feasibility map: which social-listening features we can build ourselves, which are worth it, and which aren't possible |
| `docs/assets/` | Downloads, including the PDF version of the feasibility map |

## Roadmap

- [x] **Phase 0: feasibility and workspace.** Feasibility map, team site and repository.
- [ ] **Phase 1: AI visibility tracker.** Scheduled buyer prompts against ChatGPT, Perplexity, Gemini and Claude. Tracks mentions, rank, share of voice and cited sources against competitors.
- [ ] **Phase 2: focused listening.** News, blogs, Reddit, YouTube, Hacker News and reviews, with AI sentiment, intent and topics, a weekly briefing and alerts. Needs a GDPR review and a private dashboard first.
- [ ] **Phase 3: closed platforms.** Instagram, Facebook, TikTok and LinkedIn can't be built in-house. Decide whether to buy a vendor.

## How we work

1. Every task starts as a GitHub issue.
2. Work on a branch and open a pull request. One teammate reviews before merging into `main`.
3. Anything merged into `docs/` on `main` is published to the team site automatically.

## Ground rules: this repository is public

- **No secrets.** API keys and tokens go in GitHub Actions secrets or a local `.env` file (already git-ignored), never in commits.
- **No personal data.** No collected posts, author names or raw mentions. Only code and aggregated results.
- **No confidential material.** No customer names, internal figures or anything you wouldn't post publicly.
