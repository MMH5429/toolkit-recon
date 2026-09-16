"""Stage 6 - apply the adjudicated values and compute the honest before/after numbers.

The "after" number is deliberately not 100%. Every field in the sample has now been
ruled on against a primary source, but four of them are cases where two readings of
the same documented reality are both defensible, and saying so is more useful than
rounding it up.
"""
from __future__ import annotations

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"

FIELD_MAP = {"mcp_status": ("mcp", "status")}
EXTRA_NOTES = {
    41: "Shopify removed admin-created custom apps; the single-store path is now a Dev Dashboard/CLI app with custom distribution (no Shopify review).",
    50: "fanbasis.com 301-redirects to commas.com - the product rebranded to Commas. Marketing mentions APIs and SDKs; no developer docs or key issuance exist.",
    80: "No webhooks: change detection must poll with updated_since. A constraint on toolkit design, not a blocker.",
    82: "Sandbox keys are instant; Production requires a reviewed Dashboard request. The MCP is for building integrations, not reading account data.",
    84: "Product could not be identified by two independent passes. Candidates found: paygent.ai, paygent.co.jp, paygent.tech - none matching 'Paygent Connect (NMI-powered)'.",
    91: "Consumer NotebookLM has no public API. Gemini Notebook Enterprise exposes Discovery Engine v1alpha notebook endpoints with a gcloud bearer token.",
    92: "Inversion worth knowing: the official MCP server is available on the free Basic plan while the REST API is Enterprise-only.",
}


def main() -> None:
    recs = {r["id"]: r for r in json.loads((D / "apps.json").read_text(encoding="utf-8"))}
    adj = json.loads((D / "verify" / "adjudications.json").read_text(encoding="utf-8"))
    score = json.loads((D / "verify" / "scorecard.json").read_text(encoding="utf-8"))

    applied = 0
    for a in adj:
        r = recs[a["id"]]
        if a["field"] in FIELD_MAP:
            outer, inner = FIELD_MAP[a["field"]]
            if r[outer][inner] != a["ship"]:
                r[outer][inner] = a["ship"]; applied += 1
        elif r[a["field"]] != a["ship"]:
            r[a["field"]] = a["ship"]; applied += 1
    for _id, note in EXTRA_NOTES.items():
        recs[_id]["notes"] = note
    for a in adj:  # mark every adjudicated record so the page can show a badge
        recs[a["id"]]["adjudicated"] = True

    json.dump(sorted(recs.values(), key=lambda r: r["id"]),
              open(D / "apps.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    n = score["sample_size"]
    total = n * 5  # 5 compared fields per app
    exact = round(score["overall_exact_agreement"] / 100 * total)
    # sets that differ but overlap were never real disagreements
    overlap_only = sum(
        round((v["overlap_pct"] - v["exact_pct"]) / 100 * n) for v in score["set_fields"].values()
    )
    d = score["disagreement_count"]
    p1_wins = sum(1 for a in adj if a["winner"] == "pass1")
    p2_wins = sum(1 for a in adj if a["winner"] == "pass2")
    both = sum(1 for a in adj if a["winner"] == "both-defensible")
    survived = exact + overlap_only + p1_wins + both

    out = {
        "sample_size": n,
        "field_decisions": total,
        "pass1_exact_agreement_pct": round(exact / total * 100, 1),
        "pass1_overlap_tolerant_pct": round((exact + overlap_only) / total * 100, 1),
        "pass1_survived_adjudication_pct": round(survived / total * 100, 1),
        "corrections_applied": applied,
        "disagreements": d,
        "adjudication": {"pass1_right": p1_wins, "pass2_right": p2_wins, "both_defensible": both},
        "shipped_adjudicated_pct": 100.0,
        "caveat": (
            f"{both} of {d} disagreements are rubric ambiguity, not factual error: two "
            "defensible readings of the same documented reality. Counted in pass 1's favour "
            "because its value is what ships."
        ),
    }
    (D / "verify" / "accuracy.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"applied {applied} adjudicated corrections")
    print(f"  pass 1, exact agreement        {out['pass1_exact_agreement_pct']}%")
    print(f"  pass 1, overlap-tolerant       {out['pass1_overlap_tolerant_pct']}%")
    print(f"  pass 1, survived adjudication  {out['pass1_survived_adjudication_pct']}%")
    print(f"  adjudication: p1 {p1_wins} / p2 {p2_wins} / both-defensible {both}")


if __name__ == "__main__":
    main()
