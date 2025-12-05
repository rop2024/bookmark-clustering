# bookmark-cli/tests/test_loader.py
import json
import tempfile
from pathlib import Path
from bookmark_cli.loader import load_chrome_bookmarks, flatten_bookmarks

def test_load_chrome_bookmarks():
    # Create a mock Chrome bookmarks file
    mock_bookmarks = {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "id": "1",
                        "name": "Test Folder",
                        "type": "folder",
                        "children": [
                            {
                                "id": "2",
                                "name": "Test Bookmark",
                                "type": "url",
                                "url": "https://example.com",
                                "date_added": "1234567890"
                            }
                        ]
                    }
                ]
            }
        },
        "version": 1
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_bookmarks, f)
        temp_path = Path(f.name)
    
    try:
        loaded = load_chrome_bookmarks(temp_path)
        assert loaded["version"] == 1
        assert "roots" in loaded
    finally:
        temp_path.unlink()

def test_flatten_bookmarks():
    mock_bookmarks = {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "id": "1",
                        "name": "Test Folder",
                        "type": "folder",
                        "children": [
                            {
                                "id": "2",
                                "name": "Test Bookmark",
                                "type": "url",
                                "url": "https://example.com",
                                "date_added": "1234567890"
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    flattened = flatten_bookmarks(mock_bookmarks)
    
    assert len(flattened) == 1
    assert flattened[0]["url"] == "https://example.com"
    assert flattened[0]["parent"] == "Test Folder"
    assert flattened[0]["original_parent_id"] == "1"