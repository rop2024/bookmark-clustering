# bookmark-cli/bookmark_cli/normalizer.py
from urllib.parse import urlparse, urlunparse
from typing import List, Tuple, Dict, Any
import tldextract

def normalize_url(url: str) -> str:
    """Normalize URL for deduplication"""
    if not url or not isinstance(url, str):
        return url
    
    try:
        parsed = urlparse(url)
        
        # Lowercase scheme and hostname
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        
        # Remove default ports
        port = parsed.port
        if (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443):
            port = None
        
        # Remove trailing slash from path
        path = parsed.path.rstrip('/')
        
        # Reconstruct URL
        normalized = urlunparse((
            scheme,
            f"{hostname}{':' + str(port) if port else ''}",
            path,
            parsed.params,
            parsed.query,  # Keep query string
            parsed.fragment  # Keep fragment
        ))
        
        return normalized
    except Exception:
        # Return original if parsing fails
        return url

def deduplicate_entries(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Tuple]]:
    """Remove duplicate entries based on normalized URL"""
    # Sort by date_added (oldest first)
    sorted_entries = sorted(entries, key=lambda x: x.get('date_added', ''))
    
    url_map = {}
    deduped = []
    removed = []
    
    for entry in sorted_entries:
        if not entry.get('url'):
            # Keep entries without URL (folders/comments)
            deduped.append(entry)
            continue
        
        normalized = normalize_url(entry['url'])
        
        if normalized not in url_map:
            url_map[normalized] = entry
            deduped.append(entry)
        else:
            # This is a duplicate
            kept_entry = url_map[normalized]
            removed.append((entry, kept_entry))
    
    return deduped, removed