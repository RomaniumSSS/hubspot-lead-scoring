"""Enrichment module — swappable.

Public interface: enrich(domain) -> dict. The rest of the app calls this without
knowing HOW enrichment happens. Today it scrapes the company homepage; to switch
to a vendor API later, replace the body of enrich() — callers stay unchanged.
"""

import ipaddress
import re
import socket

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


# Domains come from contact emails — attacker-controlled once this runs as a
# webhook service. Guard against SSRF: only fetch real public hostnames, never
# IP literals or hosts resolving into private/reserved ranges (cloud metadata etc.).
HOSTNAME_RE = re.compile(
    r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)
MAX_REDIRECTS = 3


def is_safe_public_host(host: str) -> bool:
    """True only for a well-formed public hostname resolving to public IPs.

    Residual risk: DNS rebinding (host resolves public here, private on the
    actual fetch). Acceptable for local runs; revisit with pinned-IP connects
    before deploying as an internet-facing service (Step 5).
    """
    if not HOSTNAME_RE.match(host):
        return False
    try:
        addr_infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in addr_infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            return False
    return True


def domain_from_email(email: str | None) -> str | None:
    """'john@acmecorp.com' -> 'acmecorp.com'. Returns None if no usable domain."""
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].strip().lower()


def enrich(domain: str | None) -> dict:
    """Return company signals for a domain.

    Always returns a dict with a 'status' key so the caller can react:
      - 'skipped'     : free email, no domain, or unsafe/unresolvable host
      - 'ok'          : reached the site, carries 'title' and 'description'
      - 'unreachable' : host is fine but the site didn't respond
    """
    if not domain:
        return {"status": "skipped", "note": "no domain"}
    if domain in FREE_EMAIL_DOMAINS:
        return {
            "status": "skipped",
            "note": "free email provider, not a company domain",
        }

    if not is_safe_public_host(domain):
        return {"status": "skipped", "note": "invalid or non-public domain"}

    # Redirects followed by hand so every hop passes the same SSRF check —
    # a public site redirecting to an internal address must not be fetched.
    url = f"https://{domain}"
    redirects = 0
    try:
        while True:
            response = httpx.get(
                url,
                follow_redirects=False,
                timeout=8.0,
                headers={"User-Agent": "Mozilla/5.0 (lead-scoring-bot)"},
            )
            if not response.is_redirect or response.next_request is None:
                break
            if redirects >= MAX_REDIRECTS:
                return {"status": "unreachable", "note": "too many redirects"}
            redirects += 1
            next_url = response.next_request.url
            if next_url.scheme not in ("http", "https") or not is_safe_public_host(
                next_url.host
            ):
                return {"status": "skipped", "note": "redirect to unsafe location"}
            url = str(next_url)
        response.raise_for_status()
    except httpx.HTTPError as error:
        # A dead company site is expected, not a bug — report it, don't crash the run.
        return {"status": "unreachable", "note": str(error)}

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = soup.find("meta", attrs={"name": "description"})
    description = meta.get("content", "").strip() if meta else None

    # Site text is untrusted input headed for an LLM prompt — cap its size.
    return {
        "status": "ok",
        "title": title[:200] if title else None,
        "description": description[:400] if description else None,
    }


if __name__ == "__main__":
    # Quick manual check: python enrich.py
    for test_domain in [
        "anthropic.com",
        "gmail.com",
        "this-domain-does-not-exist-zzz.com",
    ]:
        print(test_domain, "->", enrich(test_domain))
