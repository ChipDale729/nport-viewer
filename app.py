"""
N-PORT Holdings Viewer — Flask Web App
--------------------------------------
Serves a simple web interface for fetching and displaying the latest
Form N-PORT holdings for a given CIK (mutual fund / ETF).

Features:
- HTML parsing fallback for filings without XML
- Rate limiting (Flask-Limiter)
- 30-minute in-memory caching
- Graceful error handling and JSON responses
"""

import os
from flask import Flask, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cachetools import TTLCache

from nport_service import fetch_latest_nport_holdings_html, HTTPError


# -------------------------------------------------------------------
# Flask App Setup
# -------------------------------------------------------------------
app = Flask(__name__)

# Rate limiter: simple in-memory storage (sufficient for dev/testing)
# For production, configure Redis or Memcached via storage_uri.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)


# -------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate-limit violations."""
    return jsonify({
        "error": "Rate limit exceeded. Try again soon.",
        "detail": getattr(e, "description", "Too many requests"),
    }), 429


# -------------------------------------------------------------------
# Simple In-Memory Cache
# -------------------------------------------------------------------
_cache = TTLCache(maxsize=128, ttl=60 * 30)  # 30-minute TTL


def cached_fetch(cik10: str):
    """Fetch N-PORT holdings, using cached data when available."""
    if cik10 in _cache:
        app.logger.info(f"[cache hit] {cik10}")
        return _cache[cik10]

    app.logger.info(f"[cache miss] {cik10}")
    data = fetch_latest_nport_holdings_html(cik10)
    _cache[cik10] = data
    return data


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.get("/")
@limiter.exempt
def index():
    """Serve main UI page."""
    return render_template("index.html")


@app.get("/api/health")
@limiter.limit("30 per minute")
def health():
    """Health-check endpoint for uptime monitoring."""
    return jsonify({"ok": True})


@app.get("/api/holdings/<cik>")
@limiter.limit("10 per minute")
def api_holdings(cik: str):
    """
    Main API endpoint.
    Returns the latest N-PORT holdings for the provided CIK.
    """
    try:
        # Normalize and validate CIK (digits only, up to 10)
        digits = "".join(c for c in cik if c.isdigit())
        if not digits or len(digits) > 10:
            return jsonify({"error": "CIK must be up to 10 digits."}), 400

        cik10 = digits.zfill(10)
        data = cached_fetch(cik10)
        return jsonify(data)

    except HTTPError as e:
        return jsonify({"error": str(e)}), getattr(e, "status", 502)
    except Exception as e:
        app.logger.exception("Unexpected error while fetching holdings")
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
