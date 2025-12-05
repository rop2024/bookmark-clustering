# bookmark-cli/tests/test_normalizer.py
import pytest
from bookmark_cli.normalizer import normalize_url, deduplicate_entries

def test_normalize_url():
    # Test basic normalization
    assert normalize_url("https://Example.com:443/path/") == "https://example.com/path"
    assert normalize_url("http://example.com:80/path") == "http://example.com/path"
    
    # Test preserving query and fragment
    assert normalize_url("https://example.com/path?query=1#fragment") == "https://example.com/path?query=1#fragment"
    
    # Test with different ports
    assert normalize_url("https://example.com:8080/path") == "https://example.com:8080/path"
    
    # Test invalid URL
    assert normalize_url("not-a-url") == "not-a-url"

def test_deduplicate_entries():
    entries = [
        {
            "id": "1",
            "url": "https://example.com/path",
            "title": "Example 1",
            "date_added": "1000"
        },
        {
            "id": "2",
            "url": "https://EXAMPLE.com/path/",  # Same after normalization
            "title": "Example 2",
            "date_added": "2000"
        },
        {
            "id": "3",
            "url": "https://other.com/path",
            "title": "Other",
            "date_added": "1500"
        }
    ]
    
    deduped, removed = deduplicate_entries(entries)
    
    assert len(deduped) == 2  # Should keep oldest of duplicates + other
    assert len(removed) == 1  # Should remove one duplicate
    
    # Oldest should be kept (id 1)
    kept_urls = [e["url"] for e in deduped]
    assert "https://example.com/path" in kept_urls
    assert "https://other.com/path" in kept_urls