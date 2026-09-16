"""Stage 4 - blind re-research of a stratified sample.

The verifier never sees pass 1's answers, so agreement between the two passes is
real evidence rather than an agent nodding along to its own earlier output. Two
things are deliberately different from pass 1:

  1. it must FETCH the vendor's own docs page, not read search snippets, and
  2. it must return a quote from that page for auth and for access tier.

Requiring a quote is what makes the second pass more accurate than the first: a
model that has to produce supporting text cannot lean on a half-remembered prior.

    python agent/verify_blind.py
"""
from __future__ import annotations

import json, os, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

try:
    import anthropic
except ImportError:
    sys.exit("pip install -r requirements.txt")

import prompts
from research_agent import extract_json_array

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERIFY = ROOT / "data" / "verify"
MODEL = os.environ.get("RECON_VERIFY_MODEL", "claude-sonnet-5")
GROUP_SIZE = 5

TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 25},
    {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 25},
]


def verify_group(client: anthropic.Anthropic, group: list[dict]) -> list[dict]:
    app_lines = "\n".join(f"{a['id']} | {a['app']} | {a['hint']}" for a in group)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        tools=TOOLS,
        extra_headers={"anthropic-beta": "web-fetch-2025-09-10"},
        messages=[{"role": "user", "content": prompts.BLIND_VERIFY_PROMPT.format(apps=app_lines)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return extract_json_array(text)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("set ANTHROPIC_API_KEY")
    sample = json.loads((ROOT / "data" / "sample.json").read_text(encoding="utf-8"))
    groups = [sample[i : i + GROUP_SIZE] for i in range(0, len(sample), GROUP_SIZE)]
    client = anthropic.Anthropic()
    VERIFY.mkdir(parents=True, exist_ok=True)

    def run(item):
        idx, group = item
        try:
            recs = verify_group(client, group)
        except Exception as exc:
            return idx, None, f"{type(exc).__name__}: {exc}"
        (VERIFY / f"blind-g{idx}.json").write_text(
            json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        return idx, len(recs), None

    with ThreadPoolExecutor(max_workers=4) as ex:
        for idx, n, err in ex.map(run, enumerate(groups, 1)):
            print(f"  {'FAIL' if err else 'ok  '}  blind-g{idx}: {err or f'{n} verified'}")


if __name__ == "__main__":
    main()
