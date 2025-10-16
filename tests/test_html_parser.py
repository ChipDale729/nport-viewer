import html_parser

def test_pick_column_map_basic():
    labels = ["Title/Name", "CUSIP", "Balance", "Value (USD)"]
    cmap = html_parser._pick_column_map(labels)
    assert cmap["name"] == 0
    assert cmap["cusip"] == 1
    assert cmap["balance"] == 2
    assert cmap["value"] == 3

def test_is_total_row_detection():
    assert html_parser._is_total_row("Total Common Stocks (Cost $123)") is True
    assert html_parser._is_total_row("Subtotal Something") is True
    assert html_parser._is_total_row("Microsoft Corp.") is False

def test_clean_name_strips_footnote():
    assert html_parser._clean_name("Alphabet Inc. (a)") == "Alphabet Inc."

def test_pick_column_map_falls_back_to_first_for_name():
    labels = ["Security Description", "Quantity", "Fair Value"]
    cmap = html_parser._pick_column_map(labels)
    # falls back to first column for name, still finds balance/value
    assert cmap["name"] == 0
    assert cmap["balance"] is not None
    assert cmap["value"] is not None

def test_clean_num_parentheses_negative_and_commas():
    # covers _clean_num: strip $, spaces, commas; parentheses to negative
    assert html_parser._clean_num("$ 1,234") == "1234"
    assert html_parser._clean_num("(2,500)") == "-2500"
    assert html_parser._clean_num("") == ""

def test_parse_holdings_from_html_filters_total(sample_partc_html, monkeypatch):
    class FakeResp:
        def __init__(self, text):
            self.text = text
            self.content = text.encode("utf-8")
        def raise_for_status(self): pass

    def fake_get(url, headers=None, timeout=None):
        return FakeResp(sample_partc_html)

    # <- real pytest fixture gets injected here
    monkeypatch.setattr(html_parser.requests, "get", fake_get)

    out = html_parser.parse_holdings_from_html("https://example/sec/filing.htm")
    names = [h["name"] for h in out]
    assert "Apple Inc." in names
    assert "Microsoft Corp." in names
    assert not any(n.startswith("Total") for n in names)
