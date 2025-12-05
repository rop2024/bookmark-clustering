# bookmark-cli/bookmark_cli/storage.py
import json
import sqlite3
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

class CacheStorage:
    def __init__(self, cache_path: Path = Path(".bookmark_cache")):
        self.cache_path = cache_path
        self.cache_path.mkdir(exist_ok=True)
        
        # Initialize SQLite cache
        self.db_path = cache_path / "metadata.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata_cache (
                url TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                content_type TEXT,
                status_code INTEGER,
                domain TEXT,
                last_modified TEXT,
                fetch_success BOOLEAN,
                timestamp DATETIME
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                hash TEXT PRIMARY KEY,
                response TEXT,
                timestamp DATETIME
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached metadata for URL"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM metadata_cache WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "url": row[0],
                "title": row[1],
                "description": row[2],
                "content_type": row[3],
                "status_code": row[4],
                "domain": row[5],
                "last_modified": row[6],
                "fetch_success": bool(row[7]),
                "timestamp": row[8]
            }
        return None
    
    def save_metadata(self, url: str, metadata: Dict[str, Any]):
        """Save metadata to cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO metadata_cache 
            (url, title, description, content_type, status_code, domain, last_modified, fetch_success, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            url,
            metadata.get("title"),
            metadata.get("description"),
            metadata.get("content_type"),
            metadata.get("status_code", 0),
            metadata.get("domain"),
            metadata.get("last_modified"),
            metadata.get("fetch_success", False),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()