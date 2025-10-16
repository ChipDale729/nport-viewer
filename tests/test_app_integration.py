import responses
from urllib.parse import urljoin

def _wire_sec_mocks(responses_lib, cik10, submissions_json, sample_html):
    cik_stripped = str(int(cik10))
    accession = submissions_json["filings"]["recent"]["accessionNumber"][0]
    acc_nodash = accession.replace("-", "")
    primary = submissions_json["filings"]["recent"]["primaryDocument"][0]

    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses_lib.add(responses_lib.GET, subs_url, json=submissions_json, status=200)

    folder = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_nodash}/"
    idx_url = urljoin(folder, "index.json")
    responses_lib.add(responses_lib.GET, idx_url, json={"directory": {"item": [{"name": primary}]}}, status=200)

    filing_html_url = urljoin(folder, primary)
    responses_lib.add(responses_lib.GET, filing_html_url, body=sample_html, status=200, content_type="text/html")

@responses.activate
def test_api_holdings_success(app_client, submissions_json, sample_partc_html):
    cik = "0000884394"
    _wire_sec_mocks(responses, cik, submissions_json, sample_partc_html)

    resp = app_client.get(f"/api/holdings/{cik}")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["cik"] == cik
    assert payload["count"] >= 2
    names = [h["name"] for h in payload["holdings"]]
    assert "Apple Inc." in names and "Microsoft Corp." in names

def test_api_holdings_bad_cik(app_client):
    resp = app_client.get("/api/holdings/not-a-cik")
    assert resp.status_code == 400
    assert "CIK" in resp.get_json().get("error", "") or "numeric" in resp.get_json().get("error", "")

@responses.activate
def test_api_holdings_cache_hit(app_client, submissions_json, sample_partc_html):
    # first call wires mocks and populates cache
    cik = "0000884394"
    _wire_sec_mocks(responses, cik, submissions_json, sample_partc_html)
    first = app_client.get(f"/api/holdings/{cik}")
    assert first.status_code == 200

    # second call should hit your in-memory cache; we can return 500 from SEC to prove we didn’t call it
    responses.reset()
    second = app_client.get(f"/api/holdings/{cik}")
    assert second.status_code == 200
    # If you want, assert same payload shape
