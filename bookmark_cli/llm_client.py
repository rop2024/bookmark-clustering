# bookmark-cli/bookmark_cli/llm_client.py
import json
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from .gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "gemini",  # Default to Gemini
        model: str = "gemini-1.5-flash",
        base_url: Optional[str] = None,
        use_local: bool = False  # Removed local option
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.is_local = False
        
        if provider == "gemini":
            if not api_key:
                raise ValueError("Gemini API key is required. Set GEMINI_API_KEY in .env")
            self.client = GeminiClient(api_key=api_key, model_name=model)
        elif provider == "openai":
            self.base_url = base_url or "https://api.openai.com/v1"
        elif provider == "anthropic":
            self.base_url = base_url or "https://api.anthropic.com/v1"
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
    def _get_base_url(self) -> str:
        """Get API base URL based on provider"""
        if self.provider == "openai":
            return "https://api.openai.com/v1"
        elif self.provider == "anthropic":
            return "https://api.anthropic.com/v1"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def categorize_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Categorize a batch of bookmarks using LLM"""
        
        system_prompt = self._get_system_prompt()
        user_prompt = json.dumps(batch, ensure_ascii=False)
        
        # Use Gemini or other cloud APIs
        if self.provider == "gemini":
            response = await self.client.generate_json(user_prompt, system_prompt)
        elif self.provider == "openai":
            response = await self._call_openai(system_prompt, user_prompt)
        elif self.provider == "anthropic":
            response = await self._call_anthropic(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        try:
            if not isinstance(response, list):
                response = [response] if isinstance(response, dict) else []
            
            # Simple validation - just ensure id, folder, tags exist
            validated = []
            for item in response:
                if isinstance(item, dict) and "id" in item:
                    # Normalize the response
                    normalized = {
                        "id": item.get("id"),
                        "folder": item.get("folder", "Unsorted"),
                        "tags": item.get("tags", []),
                        "confidence": 0.7  # Default confidence
                    }
                    validated.append(normalized)
            
            # If we got no valid items, create fallback
            if not validated:
                return self._create_fallback_categorization(batch)
            
            return validated
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to parse LLM response: {type(e).__name__}: {e}")
            logger.debug(f"Response was: {response}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Return fallback categorizations
            return self._create_fallback_categorization(batch)
    
    def _get_system_prompt(self) -> str:
        """System prompt for bookmark categorization"""
        return """You are a bookmark organizer. Analyze each bookmark's title, URL, description, and domain to categorize it into a meaningful folder.

For each bookmark in the input array, return a JSON object with:
- id: same as input (required)
- folder: Descriptive category name based on content and purpose
- tags: 2-4 relevant keywords (lowercase, descriptive)

Folder naming guidelines:
- Create specific, meaningful categories (e.g., "Web Development", "AI & Machine Learning", "Design Resources")
- Group by topic, technology, or purpose
- Use title case for folder names
- Keep names concise but descriptive (2-4 words)
- Common categories: Development, Learning, News, Tools, Reference, Entertainment, Research, Documentation

Tag guidelines:
- Extract key technologies, topics, or themes
- Use lowercase, single words or short phrases
- Be specific (e.g., "python", "react", "tutorial", "api", "documentation")

Output format: JSON array with id, folder, and tags fields.

Example:
[
  {"id": "1", "folder": "Web Development", "tags": ["javascript", "react", "tutorial"]},
  {"id": "2", "folder": "AI & Machine Learning", "tags": ["chatgpt", "llm", "api"]},
  {"id": "3", "folder": "Design Resources", "tags": ["ui", "icons", "tools"]}
]"""
    
    def _validate_item(self, item: Dict[str, Any], batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and normalize a single LLM response item"""
        # Find matching entry in batch
        matching_entry = next(
            (e for e in batch if e.get("id") == item.get("id")),
            None
        )
        
        if not matching_entry:
            # Create a fallback item
            return {
                "id": item.get("id", ""),
                "category_label": "unsorted",
                "secondary_label": None,
                "primary_tag": "unsorted",
                "extra_tags": [],
                "confidence": 0.0
            }
        
        # Normalize values
        category_label = str(item.get("category_label", "")).strip()
        if not category_label:
            category_label = matching_entry.get("domain", "unsorted").split('.')[0].title()
        
        primary_tag = str(item.get("primary_tag", "")).lower()
        valid_tags = {"project", "area", "resource", "broken", "unsorted"}
        if primary_tag not in valid_tags:
            primary_tag = "unsorted"
        
        extra_tags = item.get("extra_tags", [])
        if isinstance(extra_tags, str):
            extra_tags = [tag.strip().lower() for tag in extra_tags.split(",")]
        elif isinstance(extra_tags, list):
            extra_tags = [str(tag).strip().lower() for tag in extra_tags]
        
        confidence = float(item.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "id": item.get("id", matching_entry["id"]),
            "category_label": category_label[:50],
            "secondary_label": str(item.get("secondary_label", "")).strip()[:30] or None,
            "primary_tag": primary_tag,
            "extra_tags": extra_tags[:10],  # Limit to 10 tags
            "confidence": round(confidence, 2)
        }
    
    def _create_fallback_categorization(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create fallback categorization when LLM fails"""
        fallback = []
        for entry in batch:
            # Extract domain from URL if available
            url = entry.get("url", "")
            folder = "Unsorted"
            
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    if domain:
                        folder = domain.split('.')[0].title()
                except:
                    pass
            
            if folder == "Unsorted" and entry.get("domain"):
                domain = entry.get("domain", "").split('.')[0]
                if domain:
                    folder = domain.title()
            
            if not folder or folder == "Unsorted":
                folder = entry.get("original_folder", "Unsorted")
            
            fallback.append({
                "id": entry.get("id", ""),
                "folder": folder,
                "tags": [],
                "confidence": 0.3
            })
        return fallback
    
    # Keep existing _call_openai and _call_anthropic methods...