"""Stage 1 - the research agent.

One agent per category, ten apps per agent, run in parallel. Each agent gets the
server-side web_search tool and is scored on returning schema-valid JSON whose
evidence URLs actually resolve (stage 3 checks that mechanically).

Why per-category and not per-app: the category note is where most of the accuracy
comes from. Telling the agent up front that "this category is full of app-review
gates" changes the answers far more than any amount of re-prompting per app.

    python agent/research_agent.py                  # all 10 categories
    python agent/research_agent.py --category "Ecommerce"
    python agent/research_agent.py --limit 2        # smoke test
"""
from __future__ import annotations

import argparse, collections, csv, json, os, pathlib, re, sys
from concurrent.futures import ThreadPoolExecutor

try:
    import anthropic
except ImportError:
    sys.exit("pip install -r requirements.txt  (anthropic SDK missing)")

import prompts

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MODEL = os.environ.get("RECON_MODEL", "claude-sonnet-5")
MAX_SEARCHES = int(os.environ.get("RECON_MAX_SEARCHES", "30"))

SLUGS = {
    "CRM and Sales": "01-crm-sales",
    "Support and Helpdesk": "02-support-helpdesk",
    "Communications and Messaging": "03-communications",
    "Marketing, Ads, Email and Social": "04-marketing-ads",
    "Ecommerce": "05-ecommerce",
    "Data, SEO and Scraping": "06-data-seo-scraping",
    "Developer, Infra and Data platforms": "07-developer-infra",
    "Productivity and Project Management": "08-productivity-pm",
    "Finance and Fintech": "09-finance-fintech",
    "AI, Research and Media-native": "10-ai-research-media",
}

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": MAX_SEARCHES,
}


def load_apps(limit: int | None = None) -> dict[str, list[dict]]:
    by_cat: dict[str, list[dict]] = collections.defaultdict(list)
    with open(pathlib.Path(__file__).parent / "apps_input.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["id"] = int(row["id"])
            by_cat[row["category"]].append(row)
    if limit:
        by_cat = {k: v[:limit] for k, v in by_cat.items()}
    return by_cat


def extract_json_array(text: str) -> list[dict]:
    """Models like to wrap JSON in prose or fences. Take the outermost array."""
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    if fence:
        return json.loads(fence.group(1))
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {text[:300]}")
    return json.loads(text[start : end + 1])


def research_category(client: anthropic.Anthropic, category: str, apps: list[dict]) -> list[dict]:
    app_lines = "\n".join(f"{a['id']} | {a['app']} | {a['hint']}" for a in apps)
    prompt = prompts.RESEARCH_PROMPT.format(
        category=category,
        apps=app_lines,
        schema=prompts.RECORD_SCHEMA,
        honesty=prompts.HONESTY_RULES,
        category_notes=prompts.CATEGORY_NOTES.get(category, ""),
        n=len(apps),
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        tools=[WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    recs = extract_json_array(text)

    known = {a["id"]: a for a in apps}
    for r in recs:
        r["category"] = category
        if r["id"] in known:
            r.setdefault("hint", known[r["id"]]["hint"])
    return sorted(recs, key=lambda r: r["id"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="run a single category")
    ap.add_argument("--limit", type=int, help="first N apps per category (smoke test)")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("set ANTHROPIC_API_KEY")

    by_cat = load_apps(args.limit)
    if args.category:
        if args.category not in by_cat:
            sys.exit(f"unknown category. one of: {list(by_cat)}")
        by_cat = {args.category: by_cat[args.category]}

    client = anthropic.Anthropic()
    RAW.mkdir(parents=True, exist_ok=True)

    def run(item):
        category, apps = item
        try:
            recs = research_category(client, category, apps)
        except Exception as exc:  # a failed category must not sink the run
            return category, None, f"{type(exc).__name__}: {exc}"
        out = RAW / f"{SLUGS[category]}.json"
        out.write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
        return category, len(recs), None

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for category, n, err in ex.map(run, by_cat.items()):
            print(f"  {'FAIL' if err else 'ok  '}  {category:38} {err or f'{n} records'}")


if __name__ == "__main__":
    main()
