"""Stage 8 - join the 100 against Composio's live toolkit catalog.

Two outputs:

  1. Coverage and a build queue - which of the 100 Composio already has, and which
     gaps are worth building first (uncovered x build-now x widest API surface).
  2. A fifth verification loop. Composio records the auth schemes it actually
     implements per toolkit. For every app we both cover, that is an independent
     second opinion on our researched auth_methods - not another model's, but a
     working integration's. Disagreements are reported, not silently reconciled.

Matching is on exact slug or normalized name, with a guarded fuzzy fallback. The
catalog's `search` endpoint is semantic (querying "Waterfall" returns unrelated
enrichment vendors), so it is used only to confirm a miss, never to claim a hit.

    pip install composio
    # key in .env.local (gitignored) or the environment
    python agent/composio_coverage.py
"""
from __future__ import annotations

import difflib, json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"

# Composio's scheme names -> the vocabulary used in this dataset
SCHEME_MAP = {
    "OAUTH2": "OAuth2", "OAUTH1": "other", "OAUTH1A": "other",
    "API_KEY": "API key", "BASIC": "Basic", "BASIC_WITH_JWT": "JWT",
    "BEARER_TOKEN": "Bearer/PAT", "GOOGLE_SERVICE_ACCOUNT": "JWT",
    "NO_AUTH": "none", "CALCOM_AUTH": "other", "BILLCOM_AUTH": "other",
    "COMPOSIO_LINK": "other", "SNOWFLAKE": "other",
}


def load_env() -> None:
    f = ROOT / ".env.local"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


# Hand-ruled cases the normalizer cannot decide, each checked against the
# toolkit's own description. Visible and justified rather than silently fuzzy.
#   value None  = the near-match is a DIFFERENT product; leave it uncovered.
#   "~slug"     = covered, but by a parent/suite toolkit rather than an exact one.
ALIASES = {
    "Monday.com": "monday",            # desc: "monday.com is a customizable work management platform"
    "WhatsApp Business": "whatsapp",   # desc: "Only supports WhatsApp Business accounts"
    "GoHighLevel": "highlevel",        # desc: "HighLevel provides a marketing automation and CRM platform"
    "Zoho CRM": "~zoho",               # only a generic "Zoho" suite toolkit exists; no zoho_crm slug
    "Zoho Cliq": None,                 # no cliq toolkit in the catalog; "zoho" is the suite, not Cliq
    "Salesforce Commerce Cloud": None, # catalog has salesforce + salesforce_service_cloud, no commerce
    # "plaid" is absent and fuzzy-matches "placid" (image generation) - a false
    # positive. Plaid is genuinely covered, but by the plaid_mcp toolkit.
    "Plaid": "plaid_mcp",
}


def norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def variants(app: str):
    """Name forms worth trying: 'Monday.com' -> mondaycom, monday; 'Lark (X)' -> lark."""
    base = app.split("(")[0].strip()
    for v in (app, base, base.removesuffix(".com"), base.removesuffix(".io")):
        yield norm(v)


def fetch_catalog(client):
    """Walk every page. The endpoint caps at 1000 items per call."""
    items, cursor, pages = [], None, 0
    while True:
        resp = client.toolkits.list(limit=1000, **({"cursor": cursor} if cursor else {}))
        items.extend(resp.items)
        pages += 1
        cursor = getattr(resp, "next_cursor", None)
        if not cursor or pages >= 10:
            break
    return items


def main() -> None:
    load_env()
    if not os.environ.get("COMPOSIO_API_KEY"):
        sys.exit("set COMPOSIO_API_KEY (dashboard.composio.dev -> Settings -> API Keys)")
    try:
        from composio import Composio
    except ImportError:
        sys.exit("pip install composio")

    client = Composio().client
    toolkits = fetch_catalog(client)
    by_slug = {t.slug: t for t in toolkits}
    by_name = {norm(t.name): t for t in toolkits}
    print(f"catalog: {len(toolkits)} toolkits")

    recs = json.loads((D / "apps.json").read_text(encoding="utf-8"))
    out, auth_checks, unruled = [], [], []

    for r in recs:
        hit, how = None, None
        if r["app"] in ALIASES:
            target = ALIASES[r["app"]]
            if target:  # None means "the near-match is a different product"
                hit = by_slug.get(target.lstrip("~"))
                how = "alias-parent" if target.startswith("~") else "alias"
        else:
            for n in variants(r["app"]):
                if n in by_slug:
                    hit, how = by_slug[n], "slug"; break
                if n in by_name:
                    hit, how = by_name[n], "name"; break
                # 117 toolkits ship as an MCP server rather than a REST toolkit
                if f"{n}_mcp" in by_slug:
                    hit, how = by_slug[f"{n}_mcp"], "mcp-toolkit"; break
            else:
                # Deliberately NOT auto-accepted. Blind fuzzy matching paired
                # "Plaid" with "placid" (image generation). Candidates are
                # reported for a human to rule on and promote into ALIASES.
                close = difflib.get_close_matches(norm(r["app"]), list(by_slug), n=2, cutoff=0.88)
                if close:
                    unruled.append((r["app"], close))

        row = {"id": r["id"], "app": r["app"], "category": r["category"],
               "covered": bool(hit), "match": how,
               "toolkit_slug": hit.slug if hit else None,
               "toolkit_name": hit.name if hit else None,
               "buildability": r["buildability"], "api_breadth": r["api_breadth"],
               "access_tier": r["access_tier"]}

        if hit:
            theirs_raw = list(getattr(hit, "auth_schemes", None) or [])
            theirs = {SCHEME_MAP.get(s, "other") for s in theirs_raw}
            ours = set(r["auth_methods"])
            row["composio_auth_schemes"] = theirs_raw
            # Only native toolkits are comparable. An _mcp toolkit reports DCR_OAUTH,
            # which is how the MCP *server* authenticates the client - it says nothing
            # about how the underlying app's API authenticates. Comparing them would
            # manufacture disagreements that are not disagreements.
            comparable = how != "mcp-toolkit" and "DCR_OAUTH" not in theirs_raw
            if theirs and ours and comparable:
                agree = bool(theirs & ours)
                auth_checks.append({"id": r["id"], "app": r["app"], "ours": sorted(ours),
                                    "composio": theirs_raw, "agree": agree})
                row["auth_agrees"] = agree
            elif not comparable:
                row["auth_agrees"] = None  # not applicable
        out.append(row)

    (D / "composio_coverage.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (D / "composio_meta.json").write_text(json.dumps(
        {"catalog_size": len(toolkits), "mcp_toolkits_in_catalog":
         sum(1 for t in toolkits if t.slug.endswith("_mcp")),
         "run_date": __import__("datetime").date.today().isoformat()}, indent=1), encoding="utf-8")

    covered = [o for o in out if o["covered"]]
    print(f"covered: {len(covered)}/100   uncovered: {100-len(covered)}")

    agreed = sum(1 for a in auth_checks if a["agree"])
    if auth_checks:
        print(f"\nauth cross-check vs Composio's implemented schemes: "
              f"{agreed}/{len(auth_checks)} overlap ({agreed/len(auth_checks)*100:.0f}%)")
        for a in auth_checks:
            if not a["agree"]:
                print(f"  MISMATCH {a['id']:3} {a['app'][:24]:24} ours={a['ours']} composio={a['composio']}")

    if unruled:
        print("\nfuzzy candidates left UNRULED (not counted as covered):")
        for app, cands in unruled:
            print(f"  {app:26} ~ {cands}")

    rank = {"broad": 0, "moderate": 1, "narrow": 2, "minimal": 3, "none": 4}
    queue = sorted((o for o in out if not o["covered"] and o["buildability"] == "build-now"),
                   key=lambda o: rank.get(o["api_breadth"], 9))
    print(f"\nbuild queue - uncovered, build-now, widest surface first ({len(queue)}):")
    for o in queue:
        print(f"  {o['id']:3} {o['app'][:26]:26} {o['api_breadth']:9} {o['access_tier']}")

    outreach = [o for o in out if not o["covered"] and o["buildability"] in ("needs-outreach", "not-buildable-today")]
    print(f"\nnot worth code yet - uncovered and blocked on a human ({len(outreach)}):")
    for o in outreach:
        print(f"  {o['id']:3} {o['app'][:26]:26} {o['buildability']}")


if __name__ == "__main__":
    main()
