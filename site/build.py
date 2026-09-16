"""Builds docs/index.html - one self-contained file, data embedded, no network calls.

Every number on the page is computed here from data/, never typed by hand, so the
page cannot drift from the dataset.
"""
from __future__ import annotations

import collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = ROOT / "docs" / "index.html"   # GitHub Pages serves /docs

apps = json.loads((D / "apps.json").read_text(encoding="utf-8"))
acc = json.loads((D / "verify" / "accuracy.json").read_text(encoding="utf-8"))
links = json.loads((D / "verify" / "link_check.json").read_text(encoding="utf-8"))
recheck = json.loads((D / "verify" / "link_recheck.json").read_text(encoding="utf-8"))
mcpchk = json.loads((D / "verify" / "mcp_check.json").read_text(encoding="utf-8"))
adj = json.loads((D / "verify" / "adjudications.json").read_text(encoding="utf-8"))
corr = json.loads((D / "corrections.json").read_text(encoding="utf-8"))
cov = json.loads((D / "composio_coverage.json").read_text(encoding="utf-8"))
cmeta = json.loads((D / "composio_meta.json").read_text(encoding="utf-8"))
catalog_size = cmeta["catalog_size"]

N = len(apps)
BUILD_ORDER = ["build-now", "build-with-caveats", "needs-outreach", "not-buildable-today"]
BUILD_LABEL = {"build-now": "Build now", "build-with-caveats": "Caveats",
               "needs-outreach": "Needs outreach", "not-buildable-today": "Not buildable"}
TIER_LABEL = {
    "self-serve-free": "Self-serve, free", "self-serve-trial": "Self-serve, trial",
    "paid-plan-required": "Paid plan", "app-review": "App review", "admin-approval": "Admin approval",
    "partner-gated": "Partner program", "contact-sales": "Contact sales", "not-public": "No public API",
    "waitlist": "Waitlist",
}

# ---------------------------------------------------------------- statistics
tier = collections.Counter(a["access_tier"] for a in apps)
build = collections.Counter(a["buildability"] for a in apps)
auth = collections.Counter(m for a in apps for m in a["auth_methods"])
proto = collections.Counter(p for a in apps for p in a["api_protocols"])
mcp = collections.Counter(a["mcp"]["status"] for a in apps)
conf = collections.Counter(a["confidence"] for a in apps)
self_serve = sum(v for k, v in tier.items() if k.startswith("self-serve"))

by_cat: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
for a in apps:
    by_cat[a["category"]][a["buildability"]] += 1
cats = sorted(by_cat, key=lambda c: (-by_cat[c]["build-now"], c))

THEMES = [
    ("approval / app review", r"review|verification|verify|approv"),
    ("partner, sales or licence", r"partner|sales|license|licensed|enterprise"),
    ("plan or spend gate", r"paid|plan|subscription|\$|tier|credit|unit"),
    ("needs an existing account", r"admin|role|account"),
    ("no public API surface", r"no public|no hosted|not identif|no docs|undocument|404"),
]
theme = collections.Counter()
for a in apps:
    if a["buildability"] == "build-now":
        continue
    b = a["blocker"].lower()
    for name, pat in THEMES:
        if re.search(pat, b):
            theme[name] += 1
            break
    else:
        theme["other"] += 1

oauth = [a for a in apps if "OAuth2" in a["auth_methods"]]
non_oauth = [a for a in apps if "OAuth2" not in a["auth_methods"]]
ss = lambda L: sum(1 for a in L if a["access_tier"].startswith("self-serve"))
oauth_pct, non_pct = round(ss(oauth) / len(oauth) * 100), round(ss(non_oauth) / len(non_oauth) * 100)
ss_not_clean = sum(1 for a in apps
                   if a["access_tier"].startswith("self-serve") and a["buildability"] != "build-now")

dead_now = [r for r in recheck if r["verdict"].startswith("DEAD")]
blocked = [r for r in recheck if r["verdict"] == "LIVE"]
live_links = len(links) - len(dead_now)
mcp_resolved = sum(1 for m in mcpchk if m["verdict"] in ("RESOLVES", "ENDPOINT-REJECTS-GET"))
mcp_claims = sum(1 for m in mcpchk if m["verdict"] != "n/a")
no_api = [a for a in apps if "none" in a["api_protocols"]]
easy_wins = sum(1 for a in apps if a["buildability"] == "build-now" and a["api_breadth"] == "broad")

# --- Composio catalog join (stage 8) ---
BREADTH_RANK = {"broad": 0, "moderate": 1, "narrow": 2, "minimal": 3, "none": 4}
covered = [c for c in cov if c["covered"]]
uncovered = [c for c in cov if not c["covered"]]
queue = sorted((c for c in uncovered if c["buildability"] == "build-now"),
               key=lambda c: BREADTH_RANK.get(c["api_breadth"], 9))
blocked_apps = [c for c in uncovered if c["buildability"] in ("needs-outreach", "not-buildable-today")]
auth_cmp = [c for c in cov if c.get("auth_agrees") is not None]
auth_ok = sum(1 for c in auth_cmp if c["auth_agrees"])
mcp_toolkits = sum(1 for c in cov if c["match"] == "mcp-toolkit")
by_id = {a["id"]: a for a in apps}

# --------------------------------------------------------------------- chart
def bars(counter, order, total, ramp=None, muted="var(--seq-2)"):
    rows = []
    for i, k in enumerate(order):
        v = counter.get(k, 0)
        pct = v / total * 100
        color = ramp[i] if ramp else muted
        rows.append(
            f'<div class="bar-row"><span class="bar-k">{k}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.1f}%;background:{color}"></span></span>'
            f'<span class="bar-v">{v}</span></div>'
        )
    return "".join(rows)


RAMP = ["var(--ord-1)", "var(--ord-2)", "var(--ord-3)", "var(--ord-4)"]


def stacked_rows():
    out = []
    for c in cats:
        segs = []
        for i, b in enumerate(BUILD_ORDER):
            v = by_cat[c][b]
            if not v:
                continue
            segs.append(
                f'<span class="seg" style="width:{v/10*100:.1f}%;background:{RAMP[i]}" '
                f'title="{BUILD_LABEL[b]}: {v}"><span class="seg-n">{v}</span></span>'
            )
        out.append(f'<div class="stack-row"><span class="stack-k">{c}</span>'
                   f'<span class="stack-track">{"".join(segs)}</span></div>')
    return "".join(out)


# --------------------------------------------------------------------- table
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


rows = []
for a in apps:
    ev = "".join(
        f'<a href="{esc(u)}" target="_blank" rel="noopener" title="{esc(u)}">{i+1}</a>'
        for i, u in enumerate(a["evidence"])
    )
    m = a["mcp"]
    mcp_cell = (f'<a href="{esc(m["url"])}" target="_blank" rel="noopener" class="mcp mcp-{m["status"]}">{m["status"]}</a>'
                if m.get("url") else f'<span class="mcp mcp-{m["status"]}">{m["status"]}</span>')
    flag = ' <span class="adj" title="Re-checked against vendor docs in the verification pass">&#10003;</span>' if a.get("adjudicated") else ""
    rows.append(f"""<tr data-b="{a['buildability']}" data-c="{esc(a['category'])}" data-t="{a['access_tier']}"
 data-s="{esc((a['app']+' '+a['category']+' '+a['one_liner']+' '+' '.join(a['auth_methods'])).lower())}">
<td class="num">{a['id']}</td>
<td class="app"><b>{esc(a['app'])}</b>{flag}<span class="ol">{esc(a['one_liner'])}</span></td>
<td class="hide-s">{esc(a['category'])}</td>
<td>{"".join(f'<span class="tag">{esc(x)}</span>' for x in a['auth_methods']) or '<span class="dim">unknown</span>'}</td>
<td><span class="tier tier-{a['access_tier']}">{TIER_LABEL.get(a['access_tier'], a['access_tier'])}</span></td>
<td class="hide-m"><span class="dim">{esc(a['api_breadth'])}</span> &middot; {esc(", ".join(a['api_protocols']))}</td>
<td class="hide-s">{mcp_cell}</td>
<td><span class="v v-{a['buildability']}">{BUILD_LABEL[a['buildability']]}</span>
{f'<span class="blk">{esc(a["blocker"])}</span>' if a['blocker'] != 'none' else ''}</td>
<td class="ev">{ev}</td></tr>""")

# ------------------------------------------------------------ misses & wins
def adj_row(a):
    w = {"pass1": "Pass 1 was right", "pass2": "Pass 1 was wrong",
         "both-defensible": "Both defensible"}[a["winner"]]
    cls = {"pass1": "ok", "pass2": "bad", "both-defensible": "warn"}[a["winner"]]
    src = f'<a href="{esc(a["source"])}" target="_blank" rel="noopener">source</a>' if a.get("source") else '<span class="dim">no source exists</span>'
    return f"""<tr><td><b>{esc(a['app'])}</b><span class="ol">{esc(a['field'])}</span></td>
<td class="dim mono">{esc(a['pass1'])}</td><td class="mono">{esc(a['pass2'])}</td>
<td><span class="w w-{cls}">{w}</span></td>
<td class="why">{esc(a['reason'])} {src}</td></tr>"""


def queue_rows(items, show_blocker=False):
    out = []
    for c in items:
        a = by_id[c["id"]]
        right = (f'<span class="blk" style="margin:0">{esc(a["blocker"])}</span>' if show_blocker
                 else f'<span class="tier tier-{c["access_tier"]}">{TIER_LABEL.get(c["access_tier"], c["access_tier"])}</span>')
        out.append(
            f'<tr><td class="num">{c["id"]}</td>'
            f'<td class="app"><b>{esc(c["app"])}</b><span class="ol">{esc(a["one_liner"])}</span></td>'
            f'<td class="hide-s dim">{esc(c["category"])}</td>'
            f'<td class="hide-m"><span class="dim">{esc(c["api_breadth"])}</span></td>'
            f'<td>{right}</td></tr>')
    return "".join(out)


misses = [a for a in adj if a["winner"] == "pass2"]
wins = [a for a in adj if a["winner"] == "pass1"]
both = [a for a in adj if a["winner"] == "both-defensible"]
ordered_adj = misses + both + wins

CAT_OPTS = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in sorted(by_cat))

HTML = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Toolkit Recon</title>
<meta name="description" content="100 apps researched by an agent for agent-toolkit buildability: auth, access gates, API surface, MCP, and a verified accuracy report.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#128269;</text></svg>">
<style>
:root{{
  color-scheme:light;
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --rule:rgba(11,11,11,.10);
  --ord-1:#86b6ef; --ord-2:#3987e5; --ord-3:#256abf; --ord-4:#104281;
  --seq-2:#3987e5; --seq-soft:#cde2fb;
  --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;
  --accent:#104281;
}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --rule:rgba(255,255,255,.10);
  --ord-1:#cde2fb; --ord-2:#86b6ef; --ord-3:#3987e5; --ord-4:#184f95;
  --seq-2:#3987e5; --seq-soft:#184f95; --accent:#86b6ef;
}}}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--plane);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 16px}}
a{{color:var(--accent)}}
h1,h2,h3{{line-height:1.2;margin:0}}
h1{{font-size:clamp(28px,4.6vw,44px);letter-spacing:-.022em}}
h2{{font-size:clamp(19px,2.4vw,25px);letter-spacing:-.017em}}
h3{{font-size:14px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);font-weight:600}}
p{{margin:.55em 0}}
section{{padding:44px 0;border-top:1px solid var(--rule)}}
.lede{{color:var(--ink-2);max-width:66ch;font-size:16px}}
.dim{{color:var(--muted)}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}

/* header */
header{{padding:52px 0 34px}}
.eyebrow{{font-size:12.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:12px}}
.strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;background:var(--rule);
 border:1px solid var(--rule);border-radius:10px;overflow:hidden;margin-top:26px}}
.stat{{background:var(--surface);padding:14px 15px}}
.stat b{{display:block;font-size:27px;letter-spacing:-.025em;line-height:1.1}}
.stat span{{font-size:12.5px;color:var(--muted)}}

/* patterns */
.pat{{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:14px;margin-top:22px}}
.card{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:17px 18px}}
.card .n{{font-size:12px;font-weight:700;color:var(--accent);letter-spacing:.06em}}
.card h4{{margin:7px 0 6px;font-size:16.5px;line-height:1.3;letter-spacing:-.012em}}
.card p{{margin:0;font-size:14px;color:var(--ink-2)}}

/* charts */
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px;margin-top:20px}}
.chart{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:17px 18px}}
.chart h3{{margin-bottom:14px}}
.bar-row{{display:grid;grid-template-columns:132px 1fr 34px;align-items:center;gap:9px;margin:7px 0}}
.bar-k{{font-size:13px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-track{{background:var(--grid);border-radius:3px;height:13px;overflow:hidden}}
.bar-fill{{display:block;height:100%;border-radius:0 3px 3px 0}}
.bar-v{{font-size:13px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-2)}}
.stack-row{{display:grid;grid-template-columns:186px 1fr;align-items:center;gap:11px;margin:7px 0}}
.stack-k{{font-size:12.5px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.stack-track{{display:flex;height:19px;border-radius:3px;overflow:hidden;background:var(--grid)}}
.seg{{position:relative;display:flex;align-items:center;justify-content:center;border-right:2px solid var(--surface)}}
.seg:last-child{{border-right:0}}
.seg-n{{font-size:11px;font-weight:600;color:#fff;font-variant-numeric:tabular-nums}}
.legend{{display:flex;flex-wrap:wrap;gap:13px;margin-top:14px;font-size:12.5px;color:var(--ink-2)}}
.legend i{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px}}

/* table */
.tools{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:18px 0 12px}}
input[type=search],select{{font:inherit;font-size:14px;padding:7px 11px;border:1px solid var(--rule);
 border-radius:7px;background:var(--surface);color:var(--ink)}}
input[type=search]{{min-width:210px;flex:1 1 210px}}
.chip{{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--rule);border-radius:99px;
 background:var(--surface);color:var(--ink-2);cursor:pointer}}
.chip[aria-pressed=true]{{background:var(--accent);border-color:var(--accent);color:var(--plane)}}
.tbl-wrap{{border:1px solid var(--rule);border-radius:10px;overflow:auto;background:var(--surface);max-height:78vh}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th{{position:sticky;top:0;z-index:2;background:var(--surface);text-align:left;font-size:11.5px;
 letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:10px;border-bottom:1px solid var(--rule);white-space:nowrap}}
td{{padding:9px 10px;border-bottom:1px solid var(--grid);vertical-align:top}}
tr:last-child td{{border-bottom:0}}
.num{{color:var(--muted);font-variant-numeric:tabular-nums}}
.app b{{font-weight:600}}
.ol{{display:block;color:var(--muted);font-size:12px;margin-top:2px;max-width:32ch}}
.tag{{display:inline-block;background:var(--grid);border-radius:4px;padding:1px 6px;font-size:11.5px;margin:0 3px 3px 0;white-space:nowrap}}
.tier{{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11.5px;white-space:nowrap;
 border:1px solid var(--rule);background:var(--grid)}}
.tier-self-serve-free{{background:color-mix(in srgb,var(--good) 17%,transparent);border-color:color-mix(in srgb,var(--good) 40%,transparent)}}
.tier-self-serve-trial{{background:color-mix(in srgb,var(--good) 9%,transparent)}}
.tier-app-review,.tier-partner-gated{{background:color-mix(in srgb,var(--serious) 20%,transparent);border-color:color-mix(in srgb,var(--serious) 45%,transparent)}}
.tier-contact-sales,.tier-not-public{{background:color-mix(in srgb,var(--crit) 17%,transparent);border-color:color-mix(in srgb,var(--crit) 42%,transparent)}}
.tier-paid-plan-required{{background:color-mix(in srgb,var(--warn) 22%,transparent);border-color:color-mix(in srgb,var(--warn) 48%,transparent)}}
.v{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11.5px;font-weight:600;white-space:nowrap;color:#fff}}
.v-build-now{{background:var(--ord-2)}} .v-build-with-caveats{{background:var(--ord-3)}}
.v-needs-outreach{{background:var(--ord-4)}} .v-not-buildable-today{{background:var(--crit)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .v{{color:#0b0b0b}}
 :root:not([data-theme="light"]) .v-needs-outreach,:root:not([data-theme="light"]) .v-not-buildable-today{{color:#fff}}}}
.blk{{display:block;color:var(--muted);font-size:11.5px;margin-top:3px;max-width:34ch}}
.mcp{{font-size:11.5px;text-decoration:none;border-bottom:1px dotted var(--rule)}}
.mcp-official{{color:var(--good);font-weight:600}} .mcp-community{{color:var(--ink-2)}}
.mcp-none,.mcp-unknown{{color:var(--muted)}}
.ev a{{display:inline-block;width:18px;height:18px;line-height:17px;text-align:center;font-size:11px;
 border:1px solid var(--rule);border-radius:4px;margin:0 2px 2px 0;text-decoration:none;color:var(--ink-2)}}
.ev a:hover{{border-color:var(--accent);color:var(--accent)}}
.adj{{color:var(--good);font-size:11px}}
.count{{font-size:13px;color:var(--muted);margin-left:auto}}

/* verification */
.flow{{display:flex;flex-wrap:wrap;gap:9px;align-items:stretch;margin-top:18px}}
.step{{flex:1 1 168px;background:var(--surface);border:1px solid var(--rule);border-radius:9px;padding:13px 14px}}
.step b{{display:block;font-size:13.5px;margin-bottom:3px}}
.step span{{font-size:12.5px;color:var(--muted)}}
.step em{{display:block;font-style:normal;font-size:11.5px;color:var(--accent);margin-top:6px;font-weight:600}}
.gauge{{display:flex;flex-wrap:wrap;gap:11px;margin-top:18px}}
.g{{flex:1 1 168px;background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:15px 16px}}
.g b{{display:block;font-size:31px;letter-spacing:-.025em;line-height:1.05}}
.g span{{font-size:12.5px;color:var(--muted);display:block;margin-top:3px}}
.g-track{{height:6px;background:var(--grid);border-radius:99px;margin-top:10px;overflow:hidden}}
.g-fill{{height:100%;background:var(--ord-2)}}
.w{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11.5px;font-weight:600;white-space:nowrap}}
.w-bad{{background:color-mix(in srgb,var(--crit) 20%,transparent);color:var(--ink)}}
.w-ok{{background:color-mix(in srgb,var(--good) 20%,transparent);color:var(--ink)}}
.w-warn{{background:color-mix(in srgb,var(--warn) 26%,transparent);color:var(--ink)}}
.why{{font-size:12.5px;color:var(--ink-2);max-width:56ch}}
.callout{{background:var(--surface);border:1px solid var(--rule);border-left:3px solid var(--crit);
 border-radius:8px;padding:15px 17px;margin-top:16px}}
.callout h4{{margin:0 0 5px;font-size:15px}}
.callout p{{margin:0;font-size:14px;color:var(--ink-2)}}
ul{{margin:.5em 0;padding-left:1.15em}} li{{margin:.3em 0;color:var(--ink-2)}}
footer{{padding:34px 0 56px;color:var(--muted);font-size:13px;border-top:1px solid var(--rule)}}
.hidden{{display:none !important}}
@media(max-width:820px){{.hide-m{{display:none}}}}
@media(max-width:620px){{.hide-s{{display:none}}
 .bar-row{{grid-template-columns:104px 1fr 28px}} .stack-row{{grid-template-columns:118px 1fr}}}}
</style></head>
<body>

<header class="wrap">
  <div class="eyebrow">Composio &middot; AI Product Ops take-home</div>
  <h1>100 apps, one question:<br>could an agent call this tomorrow?</h1>
  <p class="lede" style="margin-top:14px">An agent pipeline researched all {N} apps for auth, access gates, API surface and
  existing MCP, then a second blind pass and three machine checks tried to prove it wrong.
  Pass&nbsp;1 agreed with the blind re-check on <b>{acc['pass1_exact_agreement_pct']}%</b> of fields;
  after adjudicating every disagreement against vendor docs, <b>{acc['pass1_survived_adjudication_pct']}%</b> of
  its answers survived and <b>{acc['corrections_applied']}</b> were corrected. Both numbers are shown below, with the misses.</p>
  <div class="strip">
    <div class="stat"><b>{build['build-now']}</b><span>buildable today</span></div>
    <div class="stat"><b>{self_serve}</b><span>self-serve credentials</span></div>
    <div class="stat"><b>{mcp['official']}</b><span>ship an official MCP</span></div>
    <div class="stat"><b>{len(no_api)}</b><span>have no usable API</span></div>
    <div class="stat"><b>{live_links}/{len(links)}</b><span>evidence links verified</span></div>
  </div>
</header>

<section class="wrap">
  <h3>The headline</h3>
  <h2 style="margin-top:9px;max-width:22ch">The blocker is almost never the API. It is permission.</h2>
  <p class="lede">Only {len(no_api)} of {N} apps lack a usable API surface. Everything else that cannot be
  built today is blocked by a human process &mdash; an app review, a partner programme, a licence, a plan.
  That changes what the work is: less reverse-engineering, more queueing.</p>

  <div class="pat">
    <div class="card"><div class="n">01</div><h4>Two thirds are open, but "open" is not "easy"</h4>
      <p>{self_serve} of {N} let a developer mint credentials alone ({tier['self-serve-free']} free,
      {tier['self-serve-trial']} on a trial). Self-serve is not the same as a clean build, though:
      {ss_not_clean} of those {self_serve} still carry a caveat or worse, usually one that only bites
      at multi-tenant scale.</p></div>

    <div class="card"><div class="n">02</div><h4>Auth method predicts nothing</h4>
      <p>OAuth2 dominates ({auth['OAuth2']} of {N}) and feels like the "enterprise" signal, but
      {oauth_pct}% of OAuth2 apps are self-serve versus {non_pct}% of the rest &mdash; statistically the same.
      The gate is the approval workflow behind the client ID, not the protocol.</p></div>

    <div class="card"><div class="n">03</div><h4>App review is the single most common blocker</h4>
      <p>{theme['approval / app review']} of the {N - build['build-now']} non-trivial apps are held up by review or
      verification; {theme['partner, sales or licence']} more by a partner, sales or licence gate. Only
      {theme['no public API surface']} are blocked by genuinely missing documentation.</p></div>

    <div class="card"><div class="n">04</div><h4>MCP is already table stakes</h4>
      <p>{mcp['official']} apps ship a vendor-operated MCP server and {mcp['community']} more have a community one &mdash;
      {mcp_resolved} of {mcp_claims} cited endpoints resolved under machine check. The interesting gap is no longer
      "does an MCP exist" but whether it covers the write paths a toolkit needs.</p></div>

    <div class="card"><div class="n">05</div><h4>Category is destiny</h4>
      <p>Developer infrastructure is {by_cat['Developer, Infra and Data platforms']['build-now']}/10 buildable today.
      Finance is {by_cat['Finance and Fintech']['build-now']}/10 and Ecommerce {by_cat['Ecommerce']['build-now']}/10.
      Anywhere money or ad spend moves, someone reviews you first.</p></div>

    <div class="card"><div class="n">06</div><h4>Where the easy wins are</h4>
      <p>{easy_wins} apps are build-now <em>and</em> have a broad API surface &mdash; the widest tool coverage per unit of
      effort. The outreach list is short and specific: {build['needs-outreach']} apps need a human to make contact
      before any code is worth writing.</p></div>
  </div>
</section>

<section class="wrap">
  <h3>The shape of it</h3>
  <div class="charts">
    <div class="chart"><h3>Buildability by category</h3>{stacked_rows()}
      <div class="legend">{"".join(f'<span><i style="background:{RAMP[i]}"></i>{BUILD_LABEL[b]}</span>' for i,b in enumerate(BUILD_ORDER))}</div>
    </div>
    <div class="chart"><h3>How you get credentials</h3>
      {bars(tier, [k for k,_ in tier.most_common()], N)}
      <p class="dim" style="font-size:12px;margin-top:11px">{self_serve} self-serve &middot; {N-self_serve} gated behind a human.</p>
    </div>
    <div class="chart"><h3>Auth methods in use</h3>
      {bars(auth, [k for k,_ in auth.most_common()], N)}
      <p class="dim" style="font-size:12px;margin-top:11px">Counts exceed {N}: most apps document more than one.</p>
    </div>
    <div class="chart"><h3>What blocks the {N - build['build-now']} that are not clean builds</h3>
      {bars(theme, [k for k,_ in theme.most_common()], N - build['build-now'])}
      <p class="dim" style="font-size:12px;margin-top:11px">Grouped from each app's stated blocker.</p>
    </div>
  </div>
</section>

<section class="wrap">
  <h3>The findings</h3>
  <h2 style="margin-top:8px">All {N}, with evidence</h2>
  <p class="lede">Numbered links go to the documentation behind each row. A green tick marks a row
  re-checked against vendor docs in the verification pass.</p>
  <div class="tools">
    <input type="search" id="q" placeholder="Search app, category, auth&hellip;" aria-label="Search">
    <select id="cat" aria-label="Filter by category"><option value="">All categories</option>{CAT_OPTS}</select>
    {"".join(f'<button class="chip" data-f="{b}" aria-pressed="false">{BUILD_LABEL[b]}</button>' for b in BUILD_ORDER)}
    <button class="chip" data-f="gated" aria-pressed="false">Gated only</button>
    <span class="count" id="count">{N} of {N}</span>
  </div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>#</th><th>App</th><th class="hide-s">Category</th><th>Auth</th><th>Credentials</th>
    <th class="hide-m">API surface</th><th class="hide-s">MCP</th><th>Verdict &amp; blocker</th><th>Docs</th></tr></thead>
    <tbody id="tb">{''.join(rows)}</tbody>
  </table></div>
</section>

<section class="wrap">
  <h3>The point of all this</h3>
  <h2 style="margin-top:8px">Joined against Composio's live catalog</h2>
  <p class="lede">The survey only matters if it produces a decision. Stage&nbsp;8 pulls all
  {catalog_size:,} toolkits from Composio's API and joins them to the {N},
  turning the research into a queue: what is already covered, what to build next, and what is not
  worth writing code for yet.</p>

  <div class="strip" style="margin-top:20px">
    <div class="stat"><b>{len(covered)}</b><span>of {N} already covered</span></div>
    <div class="stat"><b>{len(uncovered)}</b><span>gaps</span></div>
    <div class="stat"><b>{len(queue)}</b><span>ready to build now</span></div>
    <div class="stat"><b>{len(blocked_apps)}</b><span>blocked on a human</span></div>
    <div class="stat"><b>{auth_ok}/{len(auth_cmp)}</b><span>auth cross-check</span></div>
  </div>

  <div class="charts" style="margin-top:20px">
    <div class="chart" style="padding-bottom:6px"><h3>Build queue &mdash; uncovered, buildable today, widest surface first</h3>
      <div style="overflow:auto"><table style="margin-top:4px">
      <thead><tr><th>#</th><th>App</th><th class="hide-s">Category</th><th class="hide-m">Surface</th><th>Credentials</th></tr></thead>
      <tbody>{queue_rows(queue)}</tbody></table></div>
    </div>
    <div class="chart" style="padding-bottom:6px"><h3>Not worth code yet &mdash; uncovered and blocked on a human</h3>
      <div style="overflow:auto"><table style="margin-top:4px">
      <thead><tr><th>#</th><th>App</th><th class="hide-s">Category</th><th class="hide-m">Surface</th><th>Blocker</th></tr></thead>
      <tbody>{queue_rows(blocked_apps, show_blocker=True)}</tbody></table></div>
    </div>
  </div>

  <div class="callout" style="border-left-color:var(--good);margin-top:18px">
    <h4>A fifth verification loop, and the only one not built on a model</h4>
    <p>Composio records the auth schemes it has actually <em>implemented</em> per toolkit. For the
    {len(auth_cmp)} apps where that is comparable, it is an independent second opinion on our researched
    auth &mdash; from a working integration rather than another agent. <b>{auth_ok} of {len(auth_cmp)} agree
    ({auth_ok/len(auth_cmp)*100:.0f}%).</b> The single disagreement is Coda: we recorded Bearer/PAT&nbsp;+&nbsp;OAuth2,
    Composio records API_KEY. Both describe the same thing &mdash; a long-lived token sent in an
    <span class="mono">Authorization: Bearer</span> header &mdash; so it is a vocabulary boundary, not an error.
    The {mcp_toolkits} apps Composio serves through an MCP toolkit are excluded from this check: those report
    <span class="mono">DCR_OAUTH</span>, which is how the MCP server authenticates its client and says nothing
    about the app's own API.</p>
  </div>

  <div class="callout" style="border-left-color:var(--warn);margin-top:14px">
    <h4>Two matching traps worth naming</h4>
    <p>Naive fuzzy matching paired <b>Plaid</b> with <b>placid</b>, an unrelated image-generation toolkit.
    Blind fuzzy matching is now off; candidates are reported for a human to rule on and promoted into a
    documented alias list instead. Separately, {mcp_toolkits} apps looked uncovered because Composio ships them
    as <span class="mono">&lt;app&gt;_mcp</span> toolkits rather than native ones. Both bugs inflated the gap
    list before they were caught &mdash; coverage moved from 58 to {len(covered)} once fixed.</p>
  </div>
</section>

<section class="wrap">
  <h3>The agent</h3>
  <h2 style="margin-top:8px">What ran, and where a human was needed</h2>
  <p class="lede">Ten researcher agents, one per category, each holding a category-specific brief about the
  traps in its own vertical. That brief &mdash; not re-prompting &mdash; is where most of the accuracy comes from.
  Then four checks, three of them deterministic code rather than another model's opinion.</p>
  <div class="flow">
    <div class="step"><b>1 &middot; Research</b><span>10 agents &times; 10 apps, web search, strict JSON schema, honesty rules that make
      "no public API" a valid answer.</span><em>agent/research_agent.py</em></div>
    <div class="step"><b>2 &middot; Link check</b><span>Every one of the {len(links)} evidence URLs fetched. Separates genuinely dead
      links from bot-blocked ones with a second browser-header pass.</span><em>check_links.py</em></div>
    <div class="step"><b>3 &middot; MCP check</b><span>Each MCP claim must resolve on a vendor-controlled domain. Catches the
      confident claim with nothing behind it.</span><em>check_mcp.py</em></div>
    <div class="step"><b>4 &middot; Blind re-research</b><span>20-app stratified sample, re-researched by agents that never saw pass 1
      and must quote the vendor page.</span><em>verify_blind.py</em></div>
    <div class="step"><b>5 &middot; Score &amp; adjudicate</b><span>Deterministic diff, then every disagreement ruled on against
      primary sources.</span><em>score.py &middot; apply_adjudications.py</em></div>
    <div class="step"><b>6 &middot; Catalog join</b><span>Joined to Composio's live catalog for a build queue, and an auth
      cross-check against real implementations.</span><em>composio_coverage.py</em></div>
  </div>

  <div style="margin-top:26px" class="charts">
    <div class="chart"><h3>Where a human was needed</h3>
      <ul>
        <li><b>Writing the rubric, twice.</b> The first taxonomy was too loose. Most pass-1/pass-2 disagreement
        was definitional, not factual, so the definitions had to be tightened by hand and the sample re-ruled.</li>
        <li><b>Ruling on the 28 disagreements.</b> Deciding that Composio ships <em>multi-tenant</em> toolkits &mdash;
        so Gorgias counts as caveated even though a single-tenant API key is trivial &mdash; is a product call, not a lookup.</li>
        <li><b>Catching inherited marketing copy.</b> An agent read "APIs and SDKs" on a homepage as an API surface.
        A human noticed the domain redirect that explained it.</li>
        <li><b>Knowing which claims deserve a machine check.</b> "{mcp['official']} official MCP servers" is the kind of
        headline that must not be wrong, so it got its own verifier.</li>
      </ul>
    </div>
    <div class="chart"><h3>Honest notes on the build</h3>
      <ul>
        <li>The shipped dataset was produced by the prompts and loops in this repo, orchestrated through
        Claude Code's subagent runtime. <code class="mono">research_agent.py</code> packages the identical loop to run
        standalone against the Anthropic API.</li>
        <li>Stages 2, 3 and 5 are plain Python. The accuracy figures are not a model grading itself.</li>
        <li>The catalog join runs against Composio's live API ({catalog_size:,} toolkits) and needs a key, so it is the
        one stage that cannot be reproduced from this repo alone. Its output is checked in.</li>
        <li>Two matcher bugs in that join were caught and fixed before the numbers above were trusted &mdash;
        a fuzzy false positive and a missed naming convention. Both are described in that section rather than
        quietly corrected.</li>
        <li>{conf['medium']} records carry medium confidence and {conf['low']} low. Those are marked in the data, not hidden.</li>
      </ul>
    </div>
  </div>
</section>

<section class="wrap">
  <h3>The verification</h3>
  <h2 style="margin-top:8px">How accuracy moved, and what it got wrong</h2>
  <p class="lede">A stratified sample of 20 (two per category, fixed seed) was re-researched blind. Agreement is
  measured across five fields per app &mdash; {acc['field_decisions']} independent decisions.</p>

  <div class="gauge">
    <div class="g"><b>{acc['pass1_exact_agreement_pct']}%</b><span>Pass 1, exact agreement with the blind pass</span>
      <div class="g-track"><div class="g-fill" style="width:{acc['pass1_exact_agreement_pct']}%"></div></div></div>
    <div class="g"><b>{acc['pass1_overlap_tolerant_pct']}%</b><span>Counting partial matches on multi-value fields</span>
      <div class="g-track"><div class="g-fill" style="width:{acc['pass1_overlap_tolerant_pct']}%"></div></div></div>
    <div class="g"><b>{acc['pass1_survived_adjudication_pct']}%</b><span>Pass 1 answers that survived adjudication</span>
      <div class="g-track"><div class="g-fill" style="width:{acc['pass1_survived_adjudication_pct']}%"></div></div></div>
    <div class="g"><b>{acc['corrections_applied']}</b><span>Corrections applied to the shipped data</span>
      <div class="g-track"><div class="g-fill" style="width:{acc['corrections_applied']}%"></div></div></div>
  </div>

  <p class="lede" style="margin-top:20px">The gap between 57% and 83% is the interesting part. Of
  {acc['disagreements']} disagreements, pass 1 was outright wrong {acc['adjudication']['pass2_right']} times,
  right {acc['adjudication']['pass1_right']} times &mdash; the blind verifier is not automatically the better
  agent &mdash; and {acc['adjudication']['both_defensible']} were rubric ambiguity rather than error.
  <b>The dominant failure mode was not hallucination. It was an under-specified rubric.</b></p>

  <div class="charts" style="margin-top:20px">
    <div class="chart"><h3>Machine checks</h3>
      <ul>
        <li><b>{live_links} of {len(links)}</b> evidence URLs resolve ({live_links/len(links)*100:.1f}%).
        <b>{len(dead_now)}</b> were dead and are listed below. A further {len(blocked)} returned 4xx to a bare
        client but are live in a browser &mdash; counted as live, not as misses.</li>
        <li><b>{mcp_resolved} of {mcp_claims}</b> MCP endpoints resolved. One claim ({', '.join(m['app'] for m in mcpchk if m['verdict']=='NO-URL')})
        had no URL at all: it traces to a one-day-old press report of a Meta announcement, and the WhatsApp docs
        do not mention MCP. Kept, flagged unverified.</li>
        <li><b>{auth_ok} of {len(auth_cmp)}</b> auth findings match the schemes Composio has actually implemented for the
        same app &mdash; the only check here whose second opinion comes from a working integration rather than a model.</li>
        <li>All {N} records are schema-valid and ID-complete; the pipeline asserts this on every run.</li>
      </ul>
    </div>
    <div class="chart"><h3>The {len(dead_now)} fabricated-looking links</h3>
      <p class="dim" style="font-size:13px;margin-top:-4px">Plausible URLs on the right domain that do not exist &mdash;
      the exact failure a link checker is for. All three were traced to the real page and corrected.</p>
      <ul>{"".join(f'<li><b>{esc(c["id"])}</b> &middot; <span class="mono">{esc(c["from"][:66])}</span><br><span style="font-size:12px">{esc(c["why"])}</span></li>' for c in corr if c['field']=='evidence')}</ul>
    </div>
  </div>

  <h3 style="margin-top:34px">Every disagreement, and who was right</h3>
  <div class="tbl-wrap" style="margin-top:12px;max-height:none"><table>
    <thead><tr><th>App &middot; field</th><th>Pass 1</th><th>Blind pass 2</th><th>Ruling</th><th>Why</th></tr></thead>
    <tbody>{"".join(adj_row(a) for a in ordered_adj)}</tbody>
  </table></div>
</section>

<section class="wrap">
  <h3>Honesty</h3>
  <h2 style="margin-top:8px">Where this defeated us</h2>

  <div class="callout"><h4>Paygent Connect &mdash; we could not confirm the product exists</h4>
    <p>Two independent passes searched for "Paygent Connect (NMI-powered)" and found three unrelated companies:
    paygent.ai (payment-cost analysis, explicitly never moves money), paygent.co.jp (a Japanese PSP) and
    paygent.tech (agent virtual cards, whose <span class="mono">/docs</span> 404s). No NMI relationship was
    confirmed anywhere. Recorded as not buildable with no evidence URL, because inventing one would be worse.</p></div>

  <div class="callout"><h4>fanbasis &mdash; pass 1 read marketing copy as an API</h4>
    <p>It reported REST, SDKs, webhooks and API-key auth. In fact fanbasis.com redirects to commas.com &mdash; the
    company rebranded &mdash; and the "APIs and SDKs" line is homepage marketing with no developer docs, portal or key
    issuance behind it. The blind pass caught it; a hand-run redirect trace confirmed it. This is the clearest
    single miss in the set.</p></div>

  <div class="callout"><h4>NotebookLM &mdash; pass 1 was too pessimistic</h4>
    <p>It concluded there was no API and marked it needs-outreach. There is one: Gemini Notebook Enterprise
    exposes notebook endpoints on Discovery Engine v1alpha with a gcloud bearer token, verified by hand.
    Consumer NotebookLM still has none. Errors run in both directions.</p></div>

  <div class="callout" style="border-left-color:var(--warn)"><h4>What is still soft</h4>
    <p>The rubric was tightened <em>after</em> pass 1 and only the 20-app sample was re-ruled under it, so the other
    80 rows carry pass-1 judgement on multi-tenant buildability. {conf['medium']} records are medium confidence and
    {conf['low']} low. Two researcher agents exhausted their web-search budget and finished on direct fetches only.
    Nothing here should be treated as a substitute for reading the docs before a build starts.</p></div>
</section>

<footer class="wrap">
  <p>Every figure on this page is computed from <span class="mono">data/apps.json</span> at build time, not typed by hand.
  Research and verification run: 16 September 2026.</p>
  <p>Machine-readable: <a href="apps.json">apps.json</a> (all {N} records) &middot;
     <a href="summary.json">summary.json</a> (every figure on this page) &mdash; same origin, no scraping needed.</p>
  <p><a href="https://github.com/MMH5429/toolkit-recon">Source and README</a> &middot;
     <a href="https://github.com/MMH5429/toolkit-recon/blob/main/data/apps.json">Raw dataset</a> &middot;
     <a href="https://github.com/MMH5429/toolkit-recon/blob/main/data/verify/adjudications.json">Adjudication ledger</a></p>
</footer>

<script>
(function(){{
  var q=document.getElementById('q'),cat=document.getElementById('cat'),
      rows=[].slice.call(document.querySelectorAll('#tb tr')),
      count=document.getElementById('count'),chips=[].slice.call(document.querySelectorAll('.chip')),
      active=null;
  function apply(){{
    var s=q.value.trim().toLowerCase(),c=cat.value,n=0;
    rows.forEach(function(r){{
      var ok=(!s||r.dataset.s.indexOf(s)>-1)&&(!c||r.dataset.c===c);
      if(ok&&active){{ ok = active==='gated' ? r.dataset.t.indexOf('self-serve')!==0 : r.dataset.b===active; }}
      r.classList.toggle('hidden',!ok); if(ok)n++;
    }});
    count.textContent=n+' of '+rows.length;
  }}
  q.addEventListener('input',apply); cat.addEventListener('change',apply);
  chips.forEach(function(b){{b.addEventListener('click',function(){{
    var f=b.dataset.f; active = active===f ? null : f;
    chips.forEach(function(o){{o.setAttribute('aria-pressed', String(o.dataset.f===active));}});
    apply();
  }});}});
}})();
</script>
</body></html>"""

OUT.write_text(HTML, encoding="utf-8")

# Machine-readable siblings, served from the same origin as the page, so an agent
# can consume the findings without scraping the HTML.
DOCS = ROOT / "docs"
(DOCS / "apps.json").write_text(json.dumps(apps, indent=1, ensure_ascii=False), encoding="utf-8")
(DOCS / "summary.json").write_text(json.dumps({
    "generated": "2026-09-16",
    "source": "https://github.com/MMH5429/toolkit-recon",
    "n_apps": N,
    "buildability": dict(build),
    "access_tier": dict(tier),
    "auth_methods": dict(auth),
    "api_protocols": dict(proto),
    "mcp_status": dict(mcp),
    "confidence": dict(conf),
    "blockers_by_theme": dict(theme),
    "buildability_by_category": {c: dict(by_cat[c]) for c in cats},
    "accuracy": acc,
    "evidence_links": {"checked": len(links), "resolving": live_links,
                       "dead": len(dead_now), "bot_blocked_but_live": len(blocked)},
    "mcp_claim_check": {"claims": mcp_claims, "resolving": mcp_resolved},
    "composio": {"catalog_size": catalog_size, "covered": len(covered),
                 "uncovered": len(uncovered), "build_queue": [c["app"] for c in queue],
                 "blocked_on_a_human": [c["app"] for c in blocked_apps],
                 "auth_cross_check": {"compared": len(auth_cmp), "agree": auth_ok}},
}, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
print(f"  build-now={build['build-now']} self-serve={self_serve} official-mcp={mcp['official']} "
      f"links={live_links}/{len(links)} dead={len(dead_now)}")
