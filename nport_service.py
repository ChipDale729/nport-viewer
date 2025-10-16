"""
nport_service.py
----------------
Fetch the latest Form N-PORT filing (Part C: Schedule of Portfolio Investments)
for a given CIK and parse its holdings from the HTML filing.

This version is HTML-only — it does not rely on XML documents.
It automatically finds the most recent NPORT-P filing, locates the
primary HTML file, and extracts portfolio holdings using
`html_parser.parse_holdings_from_html`.

Returns structured data suitable for front-end display or API responses.
"""

import os
import re
import requests
from urllib.parse import urljoin
from html_parser import parse_holdings_from_html


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
SEC_UA = os.environ.get("SEC_USER_AGENT", "NPORT HTML Viewer (caleb.mok@hotmail.com)")
HEADERS = {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"}

SEC_BASE = "https://data.sec.gov/"
ARCHIVES_BASE = "https://www.sec.gov/Archives/"


# -------------------------------------------------------------------
# Custom Error
# -------------------------------------------------------------------
class HTTPError(RuntimeError):
    """Represents a recoverable HTTP or parsing failure."""
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


# -------------------------------------------------------------------
# Low-Level Helpers
# -------------------------------------------------------------------
def _get(url: str):
    """Perform a GET request with standard SEC headers and raise on failure."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    if not r.ok:
        raise HTTPError(f"SEC request failed ({r.status_code}) at {url}", status=r.status_code)
    return r


def _pick_latest_nport(recent: dict):
    """
    From SEC's 'recent' filings list, select the most recent NPORT-P filing.
    Returns metadata (accession, primary document, report/filing date).
    """
    forms = recent.get("form", []) or []
    for i, f in enumerate(forms):
        if (f or "").upper() == "NPORT-P":
            return {
                "accession": recent["accessionNumber"][i],
                "primary": recent["primaryDocument"][i],
                "reportDate": (recent.get("reportDate") or [None] * len(forms))[i],
                "filingDate": (recent.get("filingDate") or [None] * len(forms))[i],
            }
    return None


def _cik_stripped(cik10: str) -> str:
    """Remove leading zeros for constructing SEC Archives URLs."""
    return str(int(cik10))


def _folder_url(cik10: str, accession: str) -> str:
    """Return the SEC EDGAR folder URL for a specific accession."""
    acc_nodash = accession.replace("-", "")
    return f"{ARCHIVES_BASE}edgar/data/{_cik_stripped(cik10)}/{acc_nodash}/"


def _dir_index(folder_url: str):
    """Fetch the directory listing (index.json) for a filing folder."""
    try:
        return _get(urljoin(folder_url, "index.json")).json()
    except Exception:
        return None


def _html_candidates(folder_url: str, primary_name: str):
    """
    Identify potential HTML files in the filing folder, ordered by relevance.
    """
    idx = _dir_index(folder_url)
    names = []
    if idx:
        items = (idx.get("directory", {}) or {}).get("item", []) or []
        names = [it.get("name", "") for it in items if it.get("name")]

    cands = []
    if primary_name and primary_name.lower().endswith((".htm", ".html")):
        cands.append(primary_name)

    for n in names:
        if n.lower().endswith((".htm", ".html")) and n not in cands:
            cands.append(n)

    # Prioritize "primary" or "nport" in filename
    cands.sort(key=lambda n: (not any(k in n.lower() for k in ("primary", "nport")), n.lower()))
    return cands or ([primary_name] if primary_name else [])


def _find_primary_html_url(folder_url: str, primary_name: str) -> str:
    """
    Determine which HTML document to parse:
    1. Use primary if already HTML.
    2. Swap .xml → .html/.htm if the primary was XML.
    3. Otherwise, look for directory candidates.
    """
    # Case 1: primary already HTML
    if primary_name and primary_name.lower().endswith((".htm", ".html")):
        return urljoin(folder_url, primary_name)

    # Case 2: XML → HTML guess
    if primary_name and primary_name.lower().endswith(".xml"):
        for ext in (".html", ".htm"):
            guess = re.sub(r"\.xml$", ext, primary_name, flags=re.I)
            try:
                return _get(urljoin(folder_url, guess)).url
            except HTTPError:
                pass

    # Case 3: Directory scan
    cands = _html_candidates(folder_url, primary_name)
    if cands:
        try:
            return _get(urljoin(folder_url, cands[0])).url
        except HTTPError:
            pass

    # Fallback
    return urljoin(folder_url, primary_name)


# -------------------------------------------------------------------
# Main Service
# -------------------------------------------------------------------
def fetch_latest_nport_holdings_html(cik10: str):
    """
    Fetch and parse the latest Form N-PORT (HTML) holdings for a given CIK.

    Args:
        cik10 (str): 10-digit CIK (zero-padded if necessary)

    Returns:
        dict: {
            cik, accession, asOf, filingUrl, xmlUrl (always ""), count,
            holdings: [{cusip, name, balance, valueUsd}, ...]
        }

    Raises:
        HTTPError: on any HTTP or parsing failure
    """
    subs_url = f"{SEC_BASE}submissions/CIK{cik10}.json"
    subs = _get(subs_url).json()
    recent = subs.get("filings", {}).get("recent")
    if not recent:
        raise HTTPError("Unexpected SEC submissions shape.", status=502)

    pick = _pick_latest_nport(recent)
    if not pick:
        raise HTTPError("No public NPORT-P filings found for this CIK.", status=404)

    folder = _folder_url(cik10, pick["accession"])
    filing_html_url = _find_primary_html_url(folder, pick["primary"])

    # Parse HTML holdings
    holdings = parse_holdings_from_html(filing_html_url)
    if not holdings:
        raise HTTPError(
            f"Could not extract Part C holdings from HTML at {filing_html_url}.",
            status=502,
        )

    return {
        "cik": cik10,
        "accession": pick["accession"],
        "asOf": pick.get("reportDate") or pick.get("filingDate"),
        "filingUrl": filing_html_url,
        "xmlUrl": "",
        "count": len(holdings),
        "holdings": holdings,
    }
