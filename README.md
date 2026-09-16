# Toolkit Recon

**[Live case study →](https://mmh5429.github.io/toolkit-recon/)**

100 apps researched by an agent pipeline for one question: *could Composio ship an agent
toolkit for this tomorrow, and if not, what is actually in the way?*

Captured per app: category and one-liner, auth method(s), how a developer gets credentials,
API surface and breadth, existing MCP server, webhooks, rate limits, a buildability verdict,
the blocker, 2–4 evidence URLs, and a confidence rating.

**The headline: the blocker is almost never the API — it is permission.** Only 3 of 100 lack a
usable API surface. Of the 44 that are not clean builds, 15 are held up by app review or
verification and 10 by a partner, sales or licence gate.

## Accuracy

A 20-app stratified sample (2 per category, fixed seed) was re-researched *blind* by agents
that never saw the first pass and had to quote the vendor page. Five fields per app, 100
independent decisions:

| | |
|---|---|
| Pass 1, exact agreement with the blind pass | **57.0%** |
| Counting partial matches on multi-value fields | **72.0%** |
| Pass 1 answers that survived adjudication | **83.0%** |
| Corrections applied to the shipped data | **17** |

Of 28 disagreements, pass 1 was wrong 17 times, right 7 times, and 4 were rubric ambiguity
rather than error. The dominant failure mode was an under-specified rubric, not hallucination.
Full ruling on every disagreement, with sources: [`data/verify/adjudications.json`](data/verify/adjudications.json).

Composio's own catalog supplies a fifth, and the only check whose second opinion comes from a
working integration rather than a model: for the 60 apps where the comparison is meaningful,
**59 of our auth findings match the schemes Composio has actually implemented (98%)**. The one
disagreement is Coda — we say Bearer/PAT + OAuth2, Composio says API_KEY — which is the same
long-lived-token-in-a-bearer-header reality under two vocabularies.

Four machine checks back this up:

- **Link check** — all 385 evidence URLs fetched. 382 resolve; 3 were plausible-looking URLs
  on the right domain that do not exist, now traced to the real pages and corrected. A second
  browser-header pass separates genuinely dead links from bot-blocked ones (all 10 Meta URLs
  were bot-blocking, not fabrication).
- **MCP check** — every "official MCP" claim must resolve on a vendor-controlled domain.
  88 of 89 did. The one that did not is flagged on the page rather than dropped.
- **Schema check** — all 100 records schema-valid and ID-complete, asserted on every run.

## Against Composio's catalog

Joined to the live catalog (1,543 toolkits) to turn the survey into a decision:

| | |
|---|---|
| Already covered | **66 / 100** |
| Gaps | **34** |
| Uncovered and buildable today | **12** — the build queue |
| Uncovered and blocked on a human | **9** — outreach, not code |

## Run it

```bash
pip install -r requirements.txt

# verification stages only - deterministic, no API key needed
python agent/run_pipeline.py

# re-run the research and blind verification too
export ANTHROPIC_API_KEY=...
python agent/run_pipeline.py --full

# rebuild the page from data/
python site/build.py
```

Individual stages:

| Stage | Script | Needs a key |
|---|---|---|
| 1. Research 100 apps, 10 agents in parallel | `agent/research_agent.py` | yes |
| 2. Merge, validate, draw the sample | `agent/merge.py` | no |
| 3. Check every evidence URL | `agent/check_links.py` + `recheck_dead.py` | no |
| 4. Check every MCP claim | `agent/check_mcp.py` | no |
| 5. Blind re-research of the sample | `agent/verify_blind.py` | yes |
| 6. Score pass 1 vs pass 2 | `agent/score.py` | no |
| 7. Apply adjudications, compute accuracy | `agent/apply_adjudications.py` | no |
| 8. Composio catalog coverage → build queue + auth cross-check | `agent/composio_coverage.py` | Composio key |
| 9. Build the page | `site/build.py` | no |

`agent/prompts.py` holds the exact prompts used — including the per-category briefs, which
are where most of the first-pass accuracy comes from, and the honesty rules that make
"no public API" a valid answer rather than a failure.

## Honest notes

- The shipped dataset was produced by the prompts and loops in this repo, orchestrated through
  Claude Code's subagent runtime. `research_agent.py` packages the identical loop to run
  standalone against the Anthropic API.
- Stages 2–4 and 6–7 are plain Python, so the accuracy figures are not a model grading itself.
- Stage 8 hits Composio's live API, so it is the one stage that cannot be reproduced from this repo
  alone — you need your own `COMPOSIO_API_KEY`. Its output is checked in at
  [`data/composio_coverage.json`](data/composio_coverage.json).
- Two matcher bugs in stage 8 were caught and fixed before its numbers were trusted: blind fuzzy
  matching paired **Plaid** with **placid** (an unrelated image-generation toolkit), and 5 apps looked
  uncovered because Composio ships them as `<app>_mcp` toolkits. Coverage moved 58 → 66 once fixed.
  Fuzzy matching is now off; candidates are reported for a human to rule on and promoted into a
  documented alias list.
- The rubric was tightened *after* pass 1 and only the 20-app sample was re-ruled under it, so
  the other 80 rows carry pass-1 judgement on multi-tenant buildability.
- Two apps defeated the pipeline and are documented as such on the page: **Paygent Connect**
  (could not confirm the product exists; three unrelated "Paygent" entities found) and
  **fanbasis** (pass 1 read homepage marketing as an API surface; the domain redirects to
  commas.com after a rebrand, and no developer docs exist).

## Layout

```
agent/     pipeline: research, verification loops, scoring, prompts
data/
  raw/     one JSON file per category, straight from the research agents
  verify/  link + MCP checks, blind pass, scorecard, adjudication ledger
  apps.json    the merged, corrected, adjudicated dataset
site/      build.py  -> docs/index.html (single self-contained file)
docs/      the deployed page (GitHub Pages)
```
