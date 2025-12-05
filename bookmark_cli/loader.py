# bookmark-cli/bookmark_cli/loader.py
import json
import uuid
from typing import Dict, List, Any
from pathlib import Path
from bs4 import BeautifulSoup
import time

def load_chrome_bookmarks(filepath: Path) -> Dict[str, Any]:
    """Load Chrome bookmarks JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_chrome_bookmarks_html(filepath: Path) -> List[Dict[str, Any]]:
    """Load Chrome bookmarks HTML file and convert to flat list"""
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    bookmarks = []
    
    # Simply find all anchor tags and extract their parent folder
    all_anchors = soup.find_all('a')
    
    for anchor in all_anchors:
        url = anchor.get('href', '')
        if not url:
            continue
            
        title = anchor.get_text(strip=True)
        add_date = anchor.get('add_date', str(int(time.time())))
        
        # Try to find the parent folder by looking for H3 tags above this anchor
        parent_folder = "Root"
        dt_parent = anchor.find_parent('dt')
        if dt_parent:
            # Look backwards for the last H3 (folder)
            prev_h3 = None
            for prev in dt_parent.find_all_previous('h3'):
                prev_h3 = prev
                break
            if prev_h3:
                parent_folder = prev_h3.get_text(strip=True)
        
        bookmark = {
            'id': str(uuid.uuid4()),
            'url': url,
            'title': title,
            'date_added': add_date,
            'parent': parent_folder,
            'meta': {}
        }
        bookmarks.append(bookmark)
    
    return bookmarks

def flatten_bookmarks(bookmarks: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten nested Chrome bookmarks structure"""
    flattened = []
    
    def process_node(node: Dict[str, Any], parent_name: str = "", parent_id: str = ""):
        node_type = node.get("type", "folder")
        
        if node_type == "folder":
            folder_name = node.get("name", "")
            folder_id = node.get("id", str(uuid.uuid4()))
            
            # Process children
            children = node.get("children", [])
            for child in children:
                process_node(child, folder_name, folder_id)
        
        elif node_type == "url":
            entry = {
                "id": node.get("id", str(uuid.uuid4())),
                "url": node.get("url"),
                "title": node.get("name", ""),
                "date_added": node.get("date_added", ""),
                "parent": parent_name,
                "original_parent_id": parent_id,
                "meta": {}
            }
            flattened.append(entry)
    
    # Start processing from roots
    roots = bookmarks.get("roots", {})
    for root_key in ["bookmark_bar", "other", "synced"]:
        if root_key in roots:
            process_node(roots[root_key], root_key.replace("_", " ").title())
    
    return flattened