# bookmark-cli/bookmark_cli/gemini_client.py
import json
import httpx
from typing import Dict, Any, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class GeminiClient:
    """Client for Google Gemini API"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        # Map model names to correct API versions
        model_mapping = {
            "gemini-1.5-flash": "gemini-2.5-flash",
            "gemini-1.5-flash-latest": "gemini-2.5-flash",
            "gemini-1.5-pro": "gemini-2.5-pro",
            "gemini-pro": "gemini-pro-latest",
            "gemini-flash": "gemini-flash-latest"
        }
        self.model_name = model_mapping.get(model_name, model_name)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send prompt to Gemini and return response"""
        
        url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
        
        # Build the request payload
        # Combine system prompt and user prompt for v1beta API
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                # Extract text from response
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        if len(parts) > 0 and "text" in parts[0]:
                            return parts[0]["text"]
                
                logger.warning(f"Unexpected Gemini response format: {result}")
                return "{}"
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            raise
    
    async def generate_json(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Generate and parse JSON response from Gemini"""
        response = await self.generate(prompt, system_prompt)
        
        try:
            # Gemini should return JSON directly due to responseMimeType
            # But let's try to extract it if it's wrapped
            response = response.strip()
            
            # Try to find JSON in the response
            if response.startswith('[') or response.startswith('{'):
                return json.loads(response)
            
            # Look for JSON in markdown code blocks
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                json_str = response[start:end].strip()
                return json.loads(json_str)
            
            # Try to find any JSON
            json_start = max(response.find('['), response.find('{'))
            if json_start != -1:
                if response[json_start] == '[':
                    json_end = response.rfind(']') + 1
                else:
                    json_end = response.rfind('}') + 1
                
                if json_end > json_start:
                    json_str = response[json_start:json_end]
                    return json.loads(json_str)
            
            # If all else fails, try to parse the whole thing
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini: {e}")
            logger.debug(f"Response was: {response}")
            return []
