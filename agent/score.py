"""Stage 5 - score pass 1 against the blind pass and emit the disagreement list.

Deterministic. No model involved, so the accuracy number is not itself an
agent's opinion. Set-valued fields (auth_methods, api_protocols) are scored three
ways, because "exact match" alone understates agreement when one pass lists an
extra legitimate auth method the other skipped:

  exact    - identical sets
  overlap  - the two sets intersect at all
  jaccard  - |A n B| / |A u B|, averaged

Anything that is not an exact match on a scalar field lands in disagreements.json
for adjudication against primary sources.
"""
from __future__ import annotations

import collections, glob, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"

SCALAR = ["access_tier", "buildability"]
SETS = ["auth_methods", "api_protocols"]


def main() -> None:
    pass1 = {r["id"]: r for r in json.loads((D / "apps.json").read_text(encoding="utf-8"))}
    blind: dict[int, dict] = {}
    for f in sorted(glob.glob(str(D / "verify" / "blind-g*.json"))):
        for r in json.loads(pathlib.Path(f).read_text(encoding="utf-8")):
            blind[r["id"]] = r
    if not blind:
        raise SystemExit("no blind-g*.json found - run verify_blind.py first")

    stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    jac: dict[str, list[float]] = collections.defaultdict(list)
    disagreements = []

    for _id, b in sorted(blind.items()):
        a = pass1[_id]
        for f in SCALAR:
            hit = a[f] == b[f]
            stats[f]["hit" if hit else "miss"] += 1
            if not hit:
                disagreements.append(
                    {"id": _id, "app": a["app"], "hint": a["hint"], "field": f,
                     "pass1": a[f], "pass2": b[f],
                     "source": b.get("primary_source"),
                     "quote": b.get("quote_access") if f == "access_tier" else b.get("quote_auth"),
                     "pass2_confidence": b.get("confidence"),
                     "pass2_uncertainty": b.get("uncertainty")}
                )
        # mcp: pass 1 nests it, the verifier returns a flat string
        hit = a["mcp"]["status"] == b.get("mcp_status")
        stats["mcp_status"]["hit" if hit else "miss"] += 1
        if not hit:
            disagreements.append(
                {"id": _id, "app": a["app"], "hint": a["hint"], "field": "mcp_status",
                 "pass1": a["mcp"]["status"], "pass2": b.get("mcp_status"),
                 "source": b.get("primary_source"), "quote": a["mcp"].get("url"),
                 "pass2_confidence": b.get("confidence"), "pass2_uncertainty": b.get("uncertainty")}
            )
        for f in SETS:
            sa, sb = set(a[f]), set(b[f])
            stats[f]["exact" if sa == sb else "inexact"] += 1
            stats[f]["overlap" if sa & sb else "disjoint"] += 1
            jac[f].append(len(sa & sb) / len(sa | sb) if sa | sb else 1.0)
            if not sa & sb:
                disagreements.append(
                    {"id": _id, "app": a["app"], "hint": a["hint"], "field": f,
                     "pass1": sorted(sa), "pass2": sorted(sb),
                     "source": b.get("primary_source"), "quote": b.get("quote_auth"),
                     "pass2_confidence": b.get("confidence"), "pass2_uncertainty": b.get("uncertainty")}
                )

    n = len(blind)
    scorecard = {
        "sample_size": n,
        "sample": [{"id": i, "app": pass1[i]["app"]} for i in sorted(blind)],
        "fields": {},
        "set_fields": {},
    }
    for f in SCALAR + ["mcp_status"]:
        scorecard["fields"][f] = {"hit": stats[f]["hit"], "miss": stats[f]["miss"],
                                  "agreement": round(stats[f]["hit"] / n * 100, 1)}
    for f in SETS:
        scorecard["set_fields"][f] = {
            "exact": stats[f]["exact"], "inexact": stats[f]["inexact"],
            "exact_pct": round(stats[f]["exact"] / n * 100, 1),
            "overlap_pct": round(stats[f]["overlap"] / n * 100, 1),
            "mean_jaccard": round(sum(jac[f]) / len(jac[f]) * 100, 1),
        }
    tot_hit = sum(stats[f]["hit"] for f in SCALAR + ["mcp_status"]) + sum(stats[f]["exact"] for f in SETS)
    scorecard["overall_exact_agreement"] = round(tot_hit / (n * 5) * 100, 1)
    scorecard["disagreement_count"] = len(disagreements)

    (D / "verify" / "scorecard.json").write_text(json.dumps(scorecard, indent=1), encoding="utf-8")
    (D / "verify" / "disagreements.json").write_text(
        json.dumps(disagreements, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"sample n={n}")
    for f, v in scorecard["fields"].items():
        print(f"  {f:14} {v['agreement']:5.1f}%  ({v['hit']}/{n})")
    for f, v in scorecard["set_fields"].items():
        print(f"  {f:14} exact {v['exact_pct']:5.1f}%  overlap {v['overlap_pct']:5.1f}%  jaccard {v['mean_jaccard']:5.1f}%")
    print(f"  {'OVERALL':14} {scorecard['overall_exact_agreement']:5.1f}%   disagreements -> {len(disagreements)}")


if __name__ == "__main__":
    main()
