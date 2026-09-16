"""The exact prompts used to produce data/apps.json and data/verify/blind-*.json.

These are not a reconstruction. The strings below are the prompts that were
issued to the research and verification agents for the shipped run; run_pipeline.py
replays them against the Anthropic API so the run is reproducible outside the
harness it was first executed in.
"""

RECORD_SCHEMA = """{
 "id": int, "app": str, "category": str, "hint": str,
 "one_liner": str (<=15 words),
 "auth_methods": ["OAuth2"|"API key"|"Basic"|"Bearer/PAT"|"JWT"|"HMAC-signed"|"mTLS"|"SAML/SSO-only"|"none"|"other"],
 "auth_notes": str (<=25 words),
 "access_tier": "self-serve-free"|"self-serve-trial"|"paid-plan-required"|"admin-approval"|"app-review"|"partner-gated"|"contact-sales"|"waitlist"|"not-public",
 "credential_path": str (<=25 words, the exact steps a dev takes to get credentials),
 "api_protocols": ["REST"|"GraphQL"|"gRPC"|"SOAP"|"Webhooks"|"SDK-only"|"CLI-only"|"none"],
 "api_breadth": "broad"|"moderate"|"narrow"|"minimal"|"none",
 "breadth_note": str (<=20 words),
 "mcp": {"status": "official"|"community"|"none"|"unknown", "url": str|null, "note": str},
 "webhooks": "yes"|"no"|"limited"|"unknown",
 "rate_limits": str (<=15 words, or "undocumented"),
 "buildability": "build-now"|"build-with-caveats"|"needs-outreach"|"not-buildable-today",
 "blocker": str (<=20 words; "none" if build-now),
 "evidence": [2-4 REAL urls you actually retrieved or saw in search results],
 "confidence": "high"|"medium"|"low",
 "notes": str (<=30 words)
}"""

# The single most important part of the prompt. Without it the model produces
# confident, plausible, wrong answers -- especially invented documentation URLs.
HONESTY_RULES = """CRITICAL HONESTY RULES:
- NEVER invent a URL. Every url in "evidence" must be one you actually saw in a
  search result or successfully fetched. If you only have the docs homepage, use that.
- If you could not confirm something, set confidence "low" and say what is
  unconfirmed in "notes". Do not guess and present it as fact.
- "access_tier" is about getting API CREDENTIALS, not about using the product.
  An app that is free to use but whose API needs an Enterprise plan is "paid-plan-required".
- Note explicitly in "notes" when an app's API requires a partner/ISV program or
  app review before production use.
- "No public API" is a correct and valuable finding, not a failure. Report it plainly."""

RESEARCH_PROMPT = """You are a research agent for a Composio-style "can we build an agent
toolkit for this app?" survey. Research the apps below and write structured JSON.

For EACH app, research and determine the fields in the schema. Use 2-4 web searches or
fetches per app. Target the developer documentation, the authentication page, and the
access/pricing/partner page.

CATEGORY: {category}
APPS:
{apps}

SCHEMA (one object per app):
{schema}

{honesty}
{category_notes}

Return ONLY a valid JSON array of {n} objects."""

# Per-category steering. These encode what a human already knows is easy to get
# wrong, and they are the single biggest lever on first-pass accuracy.
CATEGORY_NOTES = {
    "Communications and Messaging": """
Pay special attention to app-review gates: Slack app distribution, Meta/WhatsApp
App Review + Business Verification, Discord bot verification. For WhatsApp Business be
precise about Cloud API vs on-prem, app review, Business Verification and phone numbers.""",
    "Marketing, Ads, Email and Social": """
This category is FULL of approval gates and they are the interesting finding. Be precise:
Google Ads developer token tiers, Meta Marketing API app review + advanced access +
Business Verification, LinkedIn Marketing Developer Platform partner vetting, Pinterest
trial vs standard access.""",
    "Ecommerce": """
Nuances: Shopify custom app (admin token, no review) vs public app (Partner + review);
Squarespace API keys gated to a Commerce plan; Amazon SP-API developer profile
registration and role qualification; Commerce Cloud and Adobe Commerce are license-gated.
'fanbasis' is obscure -- if there is genuinely no public API doc, that is the finding.""",
    "Data, SEO and Scraping": """
Nuances: check whether Ahrefs API is still Enterprise-only or now on paid plans; check
whether Clay has shipped a public API and what is Enterprise-gated; Sherlock is an
open-source CLI with NO hosted API and NO auth -- record CLI-only / auth "none".""",
    "Developer, Infra and Data platforms": """
Nuances: Neo4j -- separate the open-source DB (Bolt/Cypher, no hosted key) from the Aura
management API; this is a database protocol, not a SaaS REST API. Snowflake -- key-pair
JWT/OAuth and account-scoped URLs. MongoDB Atlas -- HTTP Digest or service accounts.
Many official MCP servers here: confirm each with a real URL, do not assume.""",
    "Productivity and Project Management": """
Nuances: Airtable legacy API keys are dead (PAT/OAuth only) -- confirm current state.
Monday.com and Linear are GraphQL-only. Smartsheet gates API access by plan. Harvest
needs a Harvest-Account-Id header.""",
    "Finance and Fintech": """
Nuances: Plaid sandbox is self-serve but Production needs review -- capture the split.
Binance uses HMAC-signed keys and Binance.US is a separate entity. Brex/Ramp need an
existing customer account with an admin role. PitchBook is likely contact-sales.
'Paygent Connect' and 'iPayX' are obscure -- if you cannot confirm the product exists as
described, say so explicitly rather than papering over it.""",
    "AI, Research and Media-native": """
This category is the hardest -- many have NO public API, which is a legitimate finding.
Do not confuse NotebookLM with the Gemini API or Vertex AI. Check whether Otter's MCP is
vendor-operated and what plan it needs. Mermaid CLI is an npm CLI: no auth, no hosted API.
For anything undocumented or reverse-engineered, say so plainly.""",
}

# Verification pass. Deliberately different in kind from pass 1: the verifier must OPEN
# the vendor's own docs and quote them, and it never sees pass 1's answer.
BLIND_VERIFY_PROMPT = """You are an INDEPENDENT VERIFICATION agent. Another agent already
researched these apps; you have NOT seen its answers and must not try to find them.
Research from scratch, from PRIMARY SOURCES ONLY, and record a supporting quote for
every claim.

For each app you must OPEN the app's own developer documentation (fetch the actual docs
page, not just read search snippets). Vendor docs > vendor blog > third-party blog. For
each field you must be able to point at a specific sentence on a vendor page.

APPS:
{apps}

For each app produce:
{{
 "id": int, "app": str,
 "auth_methods": [...], "access_tier": "...", "api_protocols": [...],
 "mcp_status": "official"|"community"|"none"|"unknown",
 "buildability": "build-now"|"build-with-caveats"|"needs-outreach"|"not-buildable-today",
 "primary_source": "the single best vendor docs URL you actually fetched",
 "quote_auth": "<=30 word snippet from the docs supporting auth_methods",
 "quote_access": "<=30 word snippet supporting access_tier",
 "fetch_ok": true|false,
 "confidence": "high"|"medium"|"low",
 "uncertainty": "<=25 words on anything you could NOT confirm"
}}

DEFINITIONS (apply strictly -- this is where two honest agents most often disagree):
  "self-serve-free"    = sign up free, generate a key/token yourself, no card, no human approval.
  "self-serve-trial"   = only obtainable during/with a time-limited trial.
  "paid-plan-required" = must be on a paid plan for API access at all.
  "admin-approval"     = needs a workspace/org admin to enable it (no vendor involvement).
  "app-review"         = vendor reviews/approves your app before production use.
  "partner-gated"      = requires joining a partner/ISV program.
  "contact-sales"      = only via a sales conversation.
  "not-public"         = no public API exists for outside developers.
For self-hosted open-source products, judge the credential path on a self-hosted or free
cloud instance. Include "Webhooks" in api_protocols only if the vendor documents outbound webhooks.

HONESTY: Never invent a URL or a quote. If a page would not load, set fetch_ok false, say
so in "uncertainty", and lower confidence. "unknown" beats a guess. A fabricated docs link
is the worst possible outcome.

Return ONLY a valid JSON array."""

ADJUDICATE_PROMPT = """Two independent research passes disagree about one app. Decide which
is right by checking the vendor's own documentation. You may fetch pages.

App: {app} ({hint})
Field in dispute: {field}
Pass 1 said: {a}
Pass 2 (blind, primary-source) said: {b}
Pass 2 cited: {source}
Pass 2 quoted: {quote}

Definitions in force:
{definitions}

Answer as JSON:
{{"winner": "pass1"|"pass2"|"both-defensible"|"neither",
  "correct_value": <the value that should ship>,
  "reason": "<=35 words",
  "source": "the vendor URL that settles it"}}

If the two answers are both defensible readings of the same documented reality (e.g. one
says self-serve because a sandbox is free, the other says app-review because production
needs approval), answer "both-defensible" and give the value that better describes
shipping a real production integration."""
