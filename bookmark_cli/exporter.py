# bookmark-cli/bookmark_cli/exporter.py
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

def export_to_chrome_format(
    entries: List[Dict[str, Any]],
    original_structure: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Export organized bookmarks to Chrome format"""
    
    # Create Chrome bookmarks structure
    chrome_bookmarks = {
        "checksum": "",
        "roots": {
            "bookmark_bar": {
                "children": [],
                "date_added": "0",
                "date_modified": "0",
                "guid": str(uuid.uuid4()),
                "id": "1",
                "name": "Bookmarks bar",
                "type": "folder"
            },
            "other": {
                "children": [],
                "date_added": "0",
                "date_modified": "0",
                "guid": str(uuid.uuid4()),
                "id": "2",
                "name": "Other bookmarks",
                "type": "folder"
            },
            "synced": {
                "children": [],
                "date_added": "0",
                "date_modified": "0",
                "guid": str(uuid.uuid4()),
                "id": "3",
                "name": "Mobile bookmarks",
                "type": "folder"
            }
        },
        "version": 1
    }
    
    # Group entries by folder
    folder_entries = defaultdict(list)
    for entry in entries:
        folder = entry.get("folder", "Unsorted")
        folder_entries[folder].append(entry)
    
    # Create folder nodes
    folder_nodes = {}
    for folder_name, folder_items in folder_entries.items():
        folder_node = {
            "children": [],
            "date_added": str(int(datetime.now().timestamp() * 1000000)),
            "date_modified": str(int(datetime.now().timestamp() * 1000000)),
            "guid": str(uuid.uuid4()),
            "id": str(len(folder_nodes) + 1000),  # Start from 1000
            "name": folder_name,
            "type": "folder"
        }
        
        # Sort items by date_added (oldest first)
        sorted_items = sorted(
            folder_items,
            key=lambda x: x.get("date_added", "0")
        )
        
        # Add bookmark items to folder
        for item in sorted_items:
            bookmark_node = {
                "date_added": item.get("date_added", "0"),
                "date_modified": item.get("date_added", "0"),
                "guid": str(uuid.uuid4()),
                "id": item.get("id", str(uuid.uuid4())),
                "name": item.get("title", "No title")[:100],
                "type": "url",
                "url": item.get("url", "")
            }
            
            # Add metadata as custom fields if needed
            if item.get("tags"):
                bookmark_node["tags"] = item.get("tags", [])[:5]
            
            folder_node["children"].append(bookmark_node)
        
        folder_nodes[folder_name] = folder_node
    
    # Add folders to bookmark bar
    for folder_node in folder_nodes.values():
        chrome_bookmarks["roots"]["bookmark_bar"]["children"].append(folder_node)
    
    # Add organizer metadata
    organizer_metadata = {
        "organizer_version": "1.0",
        "organized_at": datetime.now().isoformat(),
        "total_bookmarks": len(entries),
        "folders_created": len(folder_nodes)
    }
    
    # Add metadata as a special folder or in root
    metadata_node = {
        "children": [],
        "date_added": str(int(datetime.now().timestamp() * 1000000)),
        "date_modified": str(int(datetime.now().timestamp() * 1000000)),
        "guid": str(uuid.uuid4()),
        "id": "9999",
        "name": "Organizer Metadata",
        "type": "folder",
        "meta": organizer_metadata
    }
    
    chrome_bookmarks["roots"]["other"]["children"].append(metadata_node)
    
    return chrome_bookmarks

def export_to_chrome_html(entries: List[Dict[str, Any]]) -> str:
    """Export organized bookmarks to Chrome HTML format"""
    from collections import defaultdict
    from html import escape
    
    # Group entries by folder
    folder_entries = defaultdict(list)
    for entry in entries:
        folder = entry.get("folder", entry.get("parent", "Unsorted"))
        folder_entries[folder].append(entry)
    
    # Build HTML
    html_parts = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<!-- This is an automatically generated file.',
        '     It will be read and overwritten.',
        '     DO NOT EDIT! -->',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>Bookmarks</TITLE>',
        '<H1>Bookmarks</H1>',
        '<DL><p>'
    ]
    
    # Add each folder
    for folder_name in sorted(folder_entries.keys()):
        items = folder_entries[folder_name]
        
        # Sort items by date_added (oldest first)
        sorted_items = sorted(
            items,
            key=lambda x: x.get("date_added", "0")
        )
        
        # Add folder
        add_date = int(datetime.now().timestamp())
        html_parts.append(f'    <DT><H3 ADD_DATE="{add_date}" LAST_MODIFIED="{add_date}">{escape(folder_name)}</H3>')
        html_parts.append('    <DL><p>')
        
        # Add bookmarks in folder
        for item in sorted_items:
            url = item.get('url', '')
            title = escape(item.get('title', 'No title'))
            date_added = item.get('date_added', str(int(datetime.now().timestamp())))
            
            # Convert microseconds to seconds if needed
            try:
                date_int = int(date_added)
                if date_int > 10000000000:  # Likely microseconds
                    date_int = date_int // 1000000
                date_added = str(date_int)
            except:
                date_added = str(int(datetime.now().timestamp()))
            
            # Add tags as part of title if present
            tags = item.get('tags', [])
            if tags:
                tags_str = ' [' + ', '.join(tags[:3]) + ']'
                title += tags_str
            
            html_parts.append(f'        <DT><A HREF="{escape(url)}" ADD_DATE="{date_added}">{title}</A>')
        
        html_parts.append('    </DL><p>')
    
    html_parts.append('</DL><p>')
    
    return '\n'.join(html_parts)