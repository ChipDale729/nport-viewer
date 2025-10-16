import os
import json
import types
import pytest

# Ensure env var is set for user agent
os.environ.setdefault("SEC_USER_AGENT", "NPORT HTML Viewer (tests@example.com)")

@pytest.fixture
def sample_partc_html():
    # Minimal HTML with a Part C heading and a proper holdings table plus a total row
    return """<!doctype html>
<html><body>
  <h2>PART C — Schedule of Portfolio Investments</h2>
  <table border="1">
    <tr>
      <th>Title/Name</th><th>CUSIP</th><th>Balance</th><th>Value (USD)</th>
    </tr>
    <tr>
      <td>Apple Inc.</td><td>037833100</td><td>10,000</td><td>$1,900,000</td>
    </tr>
    <tr>
      <td>Microsoft Corp.</td><td>594918104</td><td>8,000</td><td>$2,000,000</td>
    </tr>
    <tr>
      <td>Total Common Stocks (Cost $648,915,235,137)</td><td></td><td></td><td>3,900,000</td>
    </tr>
  </table>
</body></html>"""

@pytest.fixture
def submissions_json():
    # One latest NPORT-P item; accession and primary are consistent with nport_service path math
    return {
        "filings": {
            "recent": {
                "accessionNumber": ["0001752724-25-211156"],
                "form": ["NPORT-P"],
                "primaryDocument": ["NPORT_J905_80793218_0625.htm"],
                "reportDate": ["2025-06-30"],
                "filingDate": ["2025-07-30"],
            }
        }
    }

@pytest.fixture
def app_client(monkeypatch):
    """
    Import the real Flask app from app.py but make sure the rate limiter is disabled
    and Flask is in testing mode.
    """
    import app as app_module
    app_module.app.config["TESTING"] = True

    # If Limiter is present, disable it during tests to avoid 429s
    try:
        # app_module.limiter may not exist if not imported; guard it
        if getattr(app_module, "limiter", None) is not None:
            app_module.limiter.enabled = False
    except Exception:
        pass

    with app_module.app.test_client() as client:
        yield client
