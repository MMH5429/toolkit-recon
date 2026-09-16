"""Stage 7 (optional, NOT RUN for the shipped dataset - needs a Composio API key).

Answers the question the research is actually for: of the 100 apps, which does
Composio already have a toolkit for, and which of the gaps are worth building first?

The catalog is not public (backend.composio.dev/api/v3/toolkits returns 401 without a
key), so this stage could not run for the submitted dataset. It is included because it
is the join that turns the survey into a build queue:

    pip install composio
    export COMPOSIO_API_KEY=...
    python agent/composio_coverage.py

Output: data/composio_coverage.json, and a printed build queue ordered by
(not covered) x (build-now) x (broad API surface).
"""
from __future__ import annotations

import difflib, json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"


def slug(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def main() -> None:
    if not os.environ.get("COMPOSIO_API_KEY"):
        sys.exit("set COMPOSIO_API_KEY (get one free at app.composio.dev)")
    try:
        from composio import Composio
    except ImportError:
        sys.exit("pip install composio")

    composio = Composio()
    catalog = composio.toolkits.list()
    items = getattr(catalog, "items", catalog)
    names = {}
    for t in items:
        n = getattr(t, "name", None) or getattr(t, "slug", None) or str(t)
        names[slug(n)] = n

    recs = json.loads((D / "apps.json").read_text(encoding="utf-8"))
    out = []
    for r in recs:
        s = slug(r["app"])
        hit = names.get(s)
        if not hit:  # tolerate "Monday.com" vs "monday", "Lark (Larksuite)" vs "lark"
            close = difflib.get_close_matches(s, names.keys(), n=1, cutoff=0.82)
            hit = names[close[0]] if close else None
        out.append({"id": r["id"], "app": r["app"], "category": r["category"],
                    "covered": bool(hit), "composio_toolkit": hit,
                    "buildability": r["buildability"], "api_breadth": r["api_breadth"],
                    "access_tier": r["access_tier"]})

    (D / "composio_coverage.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    covered = sum(1 for o in out if o["covered"])
    print(f"catalog toolkits: {len(names)}   covered: {covered}/100")

    rank = {"broad": 0, "moderate": 1, "narrow": 2, "minimal": 3, "none": 4}
    queue = sorted(
        (o for o in out if not o["covered"] and o["buildability"] == "build-now"),
        key=lambda o: rank.get(o["api_breadth"], 9),
    )
    print(f"\nbuild queue - not covered, build-now, widest surface first ({len(queue)}):")
    for o in queue:
        print(f"  {o['id']:3} {o['app'][:26]:26} {o['api_breadth']:9} {o['access_tier']}")


if __name__ == "__main__":
    main()
