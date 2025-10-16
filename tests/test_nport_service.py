import pytest
import responses
from urllib.parse import urljoin

import nport_service


@responses.activate
def test_fetch_latest_nport_holdings_html_ok(submissions_json, sample_partc_html):
    cik10 = "0000884394"     # SPY
    cik_stripped = "884394"  # no leading zeros
    accession = submissions_json["filings"]["recent"]["accessionNumber"][0]
    acc_nodash = accession.replace("-", "")
    primary = submissions_json["filings"]["recent"]["primaryDocument"][0]

    # 1) submissions JSON
    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses.add(responses.GET, subs_url, json=submissions_json, status=200)

    # 2) filing folder: we may fetch index.json (ok if your service doesn’t strictly need it)
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_nodash}/"
    idx_url = urljoin(folder, "index.json")
    responses.add(responses.GET, idx_url, json={"directory": {"item": [{"name": primary}]}}, status=200)

    # 3) primary HTML
    filing_html_url = urljoin(folder, primary)
    responses.add(responses.GET, filing_html_url, body=sample_partc_html, status=200, content_type="text/html")

    data = nport_service.fetch_latest_nport_holdings_html(cik10)
    assert data["cik"] == cik10
    assert data["accession"] == accession
    assert data["filingUrl"].endswith(primary)
    assert data["xmlUrl"] == ""
    assert data["count"] >= 2

    names = [h["name"] for h in data["holdings"]]
    assert "Apple Inc." in names and "Microsoft Corp." in names
    assert not any(n.startswith("Total") for n in names)


@responses.activate
def test_fetch_latest_nport_handles_non_nport_forms_with_404():
    """Verify that non-NPORT filings return an HTTPError with 404 status."""
    cik10 = "0000000001"
    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses.add(
        responses.GET,
        subs_url,
        json={
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["000-1"],
                    "primaryDocument": ["a.htm"],
                }
            }
        },
        status=200,
    )

    with pytest.raises(nport_service.HTTPError) as excinfo:
        nport_service.fetch_latest_nport_holdings_html(cik10)
    assert excinfo.value.status == 404


@responses.activate
def test_fetch_latest_nport_handles_malformed_submissions_with_502():
    """Verify that malformed SEC submissions JSON triggers a 502 HTTPError."""
    cik10 = "0000000002"
    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses.add(responses.GET, subs_url, json={}, status=200)

    with pytest.raises(nport_service.HTTPError) as excinfo:
        nport_service.fetch_latest_nport_holdings_html(cik10)
    assert excinfo.value.status == 502


@responses.activate
def test_fetch_latest_nport_parses_html_when_primary_is_xml(submissions_json, sample_partc_html):
    """Ensure service parses .htm/.html when primary document is XML."""
    cik10 = "0000884394"
    cik_stripped = str(int(cik10))
    accession = submissions_json["filings"]["recent"]["accessionNumber"][0]
    acc_nodash = accession.replace("-", "")

    submissions_json2 = {
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "form": ["NPORT-P"],
                "primaryDocument": ["primary_doc.xml"],
                "reportDate": ["2025-06-30"],
                "filingDate": ["2025-07-30"],
            }
        }
    }

    # 1) submissions JSON
    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses.add(responses.GET, subs_url, json=submissions_json2, status=200)

    folder = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_nodash}/"

    # 2) index.json may be requested (ok if empty)
    responses.add(responses.GET, urljoin(folder, "index.json"), json={"directory": {"item": []}}, status=200)

    # 3) Service may guess either primary_doc.html or primary_doc.htm
    guessed_html = urljoin(folder, "primary_doc.html")
    guessed_htm = urljoin(folder, "primary_doc.htm")
    responses.add(responses.GET, guessed_html, body=sample_partc_html, status=200, content_type="text/html")
    responses.add(responses.GET, guessed_htm, body=sample_partc_html, status=200, content_type="text/html")

    data = nport_service.fetch_latest_nport_holdings_html(cik10)
    assert data["filingUrl"].endswith("primary_doc.html") or data["filingUrl"].endswith("primary_doc.htm")
    assert data["count"] >= 2


@responses.activate
def test_fetch_latest_nport_gracefully_recovers_when_index_json_missing(submissions_json, sample_partc_html):
    """Verify that missing index.json does not break filing retrieval."""
    cik10 = "0000884394"
    cik_stripped = str(int(cik10))
    accession = submissions_json["filings"]["recent"]["accessionNumber"][0]
    acc_nodash = accession.replace("-", "")
    primary = submissions_json["filings"]["recent"]["primaryDocument"][0]

    # 1) submissions JSON
    subs_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    responses.add(responses.GET, subs_url, json=submissions_json, status=200)

    folder = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_nodash}/"

    # 2) Simulate 404 for index.json (service should tolerate it)
    responses.add(responses.GET, urljoin(folder, "index.json"), status=404)

    # 3) primary HTML
    filing_html_url = urljoin(folder, primary)
    responses.add(responses.GET, filing_html_url, body=sample_partc_html, status=200, content_type="text/html")

    data = nport_service.fetch_latest_nport_holdings_html(cik10)
    assert data["filingUrl"].endswith(primary)
    assert data["count"] >= 2
