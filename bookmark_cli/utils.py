# bookmark-cli/bookmark_cli/utils.py
import re
from urllib.parse import urlparse
from typing import List, Optional
import hashlib

def generate_id(url: str, title: str = "") -> str:
    """Generate a unique ID for a bookmark"""
    content = f"{url}:{title}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return None

def sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename"""
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Limit length
    return name[:100]

def format_timestamp(timestamp: str) -> str:
    """Format Chrome timestamp to readable date"""
    try:
        # Chrome timestamp is microseconds since 1601-01-01
        chrome_epoch = 11644473600000000  # microseconds
        unix_microseconds = int(timestamp) - chrome_epoch
        unix_seconds = unix_microseconds / 1000000
        
        from datetime import datetime
        return datetime.fromtimestamp(unix_seconds).isoformat()
    except:
        return timestamp