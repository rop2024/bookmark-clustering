# bookmark-cli/bookmark_cli/fetcher.py
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, TextColumn

class MetadataFetcher:
    """Fetch metadata from URLs"""
    
    def __init__(
        self,
        concurrency_limit: int = 10,
        timeout: int = 10,
        respect_robots: bool = True
    ):
        self.concurrency_limit = concurrency_limit
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def fetch_single(
        self,
        client: httpx.AsyncClient,
        entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch metadata for a single entry"""
        url = entry.get('url', '')
        
        if not url:
            return entry
        
        try:
            async with self.semaphore:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract metadata
                metadata = {
                    'fetched_title': self._extract_title(soup),
                    'description': self._extract_description(soup),
                    'keywords': self._extract_keywords(soup),
                    'content_snippet': self._extract_content(soup)
                }
                
                # Update entry
                entry.update(metadata)
                
        except Exception as e:
            entry['fetch_error'] = str(e)
        
        return entry
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from HTML"""
        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content']
        
        # Try title tag
        title = soup.find('title')
        if title:
            return title.get_text().strip()
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from HTML"""
        # Try og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content']
        
        # Try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        
        return None
    
    def _extract_keywords(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract keywords from HTML"""
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            return meta_keywords['content']
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup, max_length: int = 500) -> Optional[str]:
        """Extract content snippet from HTML"""
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + '...'
        
        return text if text else None
    
    async def fetch_metadata(
        self,
        entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fetch metadata for all entries"""
        async with httpx.AsyncClient() as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ) as progress:
                task = progress.add_task(
                    f"Fetching metadata for {len(entries)} entries...",
                    total=len(entries)
                )
                
                tasks = [
                    self.fetch_single(client, entry)
                    for entry in entries
                ]
                
                results = []
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    progress.update(task, advance=1)
        
        return results
