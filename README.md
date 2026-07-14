# HubSpot Lead Scoring & Enrichment Agent

Python pipeline that plugs into a HubSpot CRM and closes the loop nobody has time for manually: **pull contacts → enrich each from its company domain → score ICP fit with an LLM (explainable) → write the score back into custom CRM properties.**

```
HubSpot CRM ──> pull contacts ──> enrich (company website signals) ──> score (Claude, structured output) ──> PATCH back to HubSpot
```

Verified end-to-end on real data: junk/free-email contacts score ~5, sample contacts 20–62, a real corporate lead (`john@stripe.com`) scores 82 with the enrichment citing "financial infrastructure business" as evidence.

## Why it's built this way

- **Raw HubSpot REST API via httpx, no SDK** — deliberate: every request and JSON response is visible, which is exactly what you want when debugging a client's CRM integration.
- **Explainable scoring, not a black box.** The LLM returns a validated `{score, reason}` object (Pydantic + structured output). Every score lands in the CRM next to a human-readable reason — a rep can disagree with it, which is the point.
- **Scoring is ICP-fit, not conversion prediction.** No ground-truth conversion data — no fake precision. The score answers "does this look like our ideal customer profile and why", transparently.
- **Enrichment is a swappable interface.** `enrich(domain) -> dict` scrapes the company homepage today (httpx + BeautifulSoup); swap the body for Clearbit/Apollo later and no caller changes.
- **SSRF-guarded.** Domains come from contact emails — attacker-controlled input once this runs as a service. Only well-formed public hostnames resolving to public IPs get fetched, and redirects are re-validated hop by hop.

## Components

| File | Role |
|---|---|
| `pull_contacts.py` | Read contacts via HubSpot REST API (Bearer token, least-privilege scopes) |
| `enrich.py` | Domain → company signals (title/description), free-email skip, fail-soft on dead sites |
| `score_contacts.py` | Claude scoring with structured output → validated `LeadScore` |
| write-back | `PATCH` into custom contact properties `lead_score` + `lead_score_reason` |

## Stack

Python 3.12 · uv · httpx · BeautifulSoup · Anthropic API (structured output) · Pydantic · HubSpot REST API (Service Key auth, EU account)

## Run it

```bash
uv sync
cp .env.example .env   # HUBSPOT_TOKEN + ANTHROPIC_API_KEY
uv run python pull_contacts.py     # see raw CRM JSON
uv run python score_contacts.py    # enrich + score + write back
```

Requires a HubSpot account (free tier is enough: 1,000 contacts, 10 custom properties) with a Service Key holding `crm.objects.contacts.read/write` + `crm.schemas.contacts.write`, and two custom contact properties: `lead_score` (number), `lead_score_reason` (multi-line text).

## Status

Personal build — the full read → enrich → score → write loop works and is verified against a live HubSpot account. Next step: deploy as a webhook-triggered service so new contacts get scored on creation.
