import pytest
from bs4 import BeautifulSoup
from api.scraper import _clean, _icon_to_bool, extract_summary, extract_features


def test_clean():
    """Test text cleaning function."""
    assert _clean("  hello   world  ") == "hello world"
    assert _clean("multiple   spaces") == "multiple spaces"
    assert _clean("") == ""
    assert _clean(None) == ""


def test_icon_to_bool():
    """Test icon to boolean conversion."""
    # Mock td with check icon
    soup = BeautifulSoup('<td><span title="check-circled"></span></td>', 'html.parser')
    td = soup.find('td')
    assert _icon_to_bool(td) == "true"

    # Mock td with cross icon
    soup = BeautifulSoup('<td><span title="cross-circled"></span></td>', 'html.parser')
    td = soup.find('td')
    assert _icon_to_bool(td) == "false"

    # No icon
    soup = BeautifulSoup('<td>No icon</td>', 'html.parser')
    td = soup.find('td')
    assert _icon_to_bool(td) == ""


def test_extract_summary():
    """Test summary extraction from HTML."""
    html = """
    <div>
        <div>Summary</div>
        <div>Key1: Value1</div>
        <div>Key2: Value2</div>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = extract_summary(soup)
    expected = [
        {"summary_key": "Key1", "summary_value": "Value1"},
        {"summary_key": "Key2", "summary_value": "Value2"}
    ]
    assert result == expected


def test_extract_features():
    """Test features extraction from HTML."""
    html = """
    <div class="AccordionItemContainer">
        <span class="AccordionItemText">Interior Features</span>
        <div class="AccordionItemBody">
            <tr><td>Feature1</td><td><span title="check-circled"></span></td></tr>
            <tr><td>Feature2</td><td><span title="cross-circled"></span></td></tr>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = extract_features(soup)
    assert "Interior Features" in result
    assert len(result["Interior Features"]) == 2
    assert result["Interior Features"][0]["feature_name"] == "Feature1"
    assert result["Interior Features"][0]["feature_value"] == "true"
    assert result["Interior Features"][1]["feature_name"] == "Feature2"
    assert result["Interior Features"][1]["feature_value"] == "false"