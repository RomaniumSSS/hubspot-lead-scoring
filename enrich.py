"""Enrichment module — swappable.

Public interface: enrich(domain) -> dict. The rest of the app calls this without
knowing HOW enrichment happens. Today it scrapes the company homepage; to switch
to a vendor API later, replace the body of enrich() — callers stay unchanged.
"""

import httpx
from bs4 import BeautifulSoup

# Free email providers are not company domains — nothing to enrich.
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "gmail.pl",
    "yahoo.com",
    "icloud.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "aol.com",
    "proton.me",
    "gmx.com",
    "mail.ru",
}


def domain_from_email(email: str | None) -> str | None:
    """'john@acmecorp.com' -> 'acmecorp.com'. Returns None if no usable domain."""
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].strip().lower()


def enrich(domain: str | None) -> dict:
    """Return company signals for a domain.

    Always returns a dict with a 'status' key so the caller can react:
      - 'skipped'     : free email / no domain — not a company
      - 'ok'          : reached the site, carries 'title' and 'description'
      - 'unreachable' : domain exists but the site didn't respond
    """
    if not domain:
        return {"status": "skipped", "note": "no domain"}
    if domain in FREE_EMAIL_DOMAINS:
        return {
            "status": "skipped",
            "note": "free email provider, not a company domain",
        }

    try:
        response = httpx.get(
            f"https://{domain}",
            follow_redirects=True,
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 (lead-scoring-bot)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # A dead company site is expected, not a bug — report it, don't crash the run.
        return {"status": "unreachable", "note": str(error)}

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = soup.find("meta", attrs={"name": "description"})
    description = meta.get("content", "").strip() if meta else None

    return {"status": "ok", "title": title, "description": description}


if __name__ == "__main__":
    # Quick manual check: python enrich.py
    for test_domain in [
        "anthropic.com",
        "gmail.com",
        "this-domain-does-not-exist-zzz.com",
    ]:
        print(test_domain, "->", enrich(test_domain))
