# bookmark-cli/bookmark_cli/config.py
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import json

class Settings(BaseSettings):
    # LLM Configuration
    llm_provider: str = "gemini"  # Default to Gemini
    llm_api_key: Optional[str] = None  # Gemini API key
    llm_model: str = "gemini-2.5-flash"  # Default Gemini model
    llm_base_url: Optional[str] = None
    
    # For backward compatibility - mapped to llm_api_key
    gemini_api_key: Optional[str] = None
    
    # Fetch Configuration
    fetch_concurrency: int = 10
    respect_robots: bool = True
    timeout_seconds: int = 30
    
    # Categorization Configuration
    batch_size: int = 20  # Smaller for local models
    max_folder_size: int = 6
    min_confidence: float = 0.4  # Lower for local models
    
    # Cache Configuration
    cache_enabled: bool = True
    cache_path: Path = Path(".bookmark_cache")
    
    # Export Configuration
    preserve_original_ids: bool = True
    add_metadata_comments: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

def init_config(config_dir: Optional[Path] = None) -> Path:
    """Initialize configuration file"""
    if config_dir is None:
        config_dir = Path.home() / ".config" / "bookmark-cli"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    
    default_config = {
        "llm_provider": "gemini",
        "llm_model": "gemini-1.5-flash",
        "fetch_concurrency": 10,
        "respect_robots": True,
        "batch_size": 50,  # Gemini API handles larger batches
        "max_folder_size": 6
    }
    
    if not config_file.exists():
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    return config_file