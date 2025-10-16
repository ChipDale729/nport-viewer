"""
HTML Parser for N-PORT Filings (Part C: Schedule of Portfolio Investments)
--------------------------------------------------------------------------

This module extracts fund holdings (CUSIP, Name, Balance, Value)
from the HTML version of Form N-PORT filings hosted on the SEC EDGAR site.

It scans all tables in the filing document, detects the relevant headers,
and aggregates all holdings into a single structured list.

Key Features:
- Handles multiple tables and inconsistent column naming.
- Cleans text, numbers, and removes footnote markers.
- Skips subtotal/total rows like "Total Common Stocks (Cost ...)".
- Robust to minor variations in HTML formatting.

Example:
    holdings = parse_holdings_from_html("https://www.sec.gov/Archives/.../NPORT.htm")
"""

import re
import requests
from lxml import html

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
HEADERS = {"User-Agent": "NPORT HTML Parser (you@example.com)"}

# Common regex patterns
WS = re.compile(r"\s+")
MONEY = re.compile(r"[,\s$]+")
FOOTNOTE = re.compile(r"\s*\((?:a|b|c|d|e|f|g)\)\s*$", re.I)  # trailing (a), (b), etc.


# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
def _clean_text(s: str) -> str:
    """Normalize whitespace and strip leading/trailing spaces."""
    if s is None:
        return ""
    return WS.sub(" ", s).strip()


def _clean_name(s: str) -> str:
    """Normalize text and remove trailing footnote markers like '(a)'."""
    s = _clean_text(s)
    return FOOTNOTE.sub("", s)


def _clean_num(s: str) -> str:
    """Remove formatting and normalize numeric values."""
    s = _clean_text(s)
    if not s:
        return ""
    # Drop $, commas, and spaces
    s = MONEY.sub("", s)
    # Convert parentheses to negative numbers, e.g., (123) → -123
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return s


def _is_total_row(name: str) -> bool:
    """
    Detect subtotal or total rows that should be skipped.
    e.g., "Total Common Stocks (Cost $...)" or "Total Investments"
    """
    if not name:
        return False
    n = name.lower()
    return n.startswith("total") or "total " in n or "(cost" in n


# -------------------------------------------------------------------
# Header + Column Mapping
# -------------------------------------------------------------------
def _header_labels(table_el):
    """
    Find the header row for a holdings table.
    Returns (list of header labels, header_row_element).
    """
    rows = table_el.xpath(".//thead/tr | .//tr")
    for r in rows:
        cells = r.xpath("./th|./td")
        labels = [_clean_text(c.text_content()) for c in cells]
        joined = " ".join(labels).lower()
        if any(k in joined for k in (
            "cusip", "title", "name", "security", "issuer",
            "balance", "shares", "units", "par value", "quantity", "par",
            "value", "val usd", "valusd", "market value", "fair value"
        )):
            return labels, r
    return [], None


def _pick_column_map(labels):
    """
    Match common column names to standardized keys:
      - CUSIP
      - Name
      - Balance
      - Value (USD)
    """
    low = [lbl.lower() for lbl in labels]

    def find(*alts):
        for i, t in enumerate(low):
            if any(a in t for a in alts):
                return i
        return None

    colmap = {
        "cusip":  find("cusip"),
        "name":   find("title", "name", "security", "issuer", "investment", "description"),
        "balance":find("balance", "shares", "units", "par value", "quantity", "par"),
        "value":  find("value", "val usd", "valusd", "market value", "fair value"),
    }

    # Default: assume first column is "Name" if not explicitly labeled
    if colmap["name"] is None:
        colmap["name"] = 0

    # Must have at least one numeric column to qualify as a holdings table
    if colmap["balance"] is None and colmap["value"] is None:
        return None

    return colmap


# -------------------------------------------------------------------
# Row Iterator
# -------------------------------------------------------------------
def _iter_data_rows(table_el, header_row):
    """
    Yield <tr> elements following the header row.
    Skips blank/decorative rows.
    """
    seen_header = False
    for r in table_el.xpath(".//tr"):
        if not seen_header:
            if r is header_row:
                seen_header = True
            continue
        tds = r.xpath("./td")
        if not tds:
            continue
        if all(not _clean_text(td.text_content()) for td in tds):
            continue
        yield tds


# -------------------------------------------------------------------
# Main Parser
# -------------------------------------------------------------------
def parse_holdings_from_html(url: str):
    """
    Parse a filing’s HTML page and return a combined list of holdings
    across all relevant Part C tables.

    Returns:
        List[dict]: Each entry contains:
          { "cusip": str, "name": str, "balance": str, "valueUsd": str }
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    doc = html.fromstring(resp.content)

    holdings_all = []
    seen_keys = set()  # Used to de-duplicate (name, balance, value) rows

    for tbl in doc.xpath("//table"):
        labels, header_row = _header_labels(tbl)
        if not labels or header_row is None:
            continue

        colmap = _pick_column_map(labels)
        if not colmap:
            continue

        for tds in _iter_data_rows(tbl, header_row):
            cells = [_clean_text(td.text_content()) for td in tds]

            def get(idx):
                return "" if idx is None or idx >= len(cells) else cells[idx]

            name = _clean_name(get(colmap["name"]))
            cusip = _clean_text(get(colmap["cusip"])) if colmap.get("cusip") is not None else ""
            balance = _clean_num(get(colmap["balance"])) if colmap.get("balance") is not None else ""
            value = _clean_num(get(colmap["value"])) if colmap.get("value") is not None else ""

            # Skip empty or total rows
            if (not name and not cusip) or _is_total_row(name):
                continue

            key = (name, balance, value)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            holdings_all.append({
                "cusip": cusip,
                "name": name,
                "balance": balance,
                "valueUsd": value,
            })

    return holdings_all
