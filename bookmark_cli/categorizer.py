# bookmark-cli/bookmark_cli/categorizer.py
import asyncio
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

async def categorize_bookmarks(
    entries: List[Dict[str, Any]],
    llm_client,
    batch_size: int = 50
) -> List[Dict[str, Any]]:
    """Categorize bookmarks using LLM in batches"""
    
    # Prepare batches
    batches = []
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        
        # Prepare payload for LLM
        llm_payload = []
        for entry in batch:
            payload_item = {
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "meta": entry.get("meta_description", entry.get("meta", "")),
                "domain": entry.get("domain", ""),
                "url": entry.get("url", ""),
                "last_modified": entry.get("last_modified", ""),
                "original_folder": entry.get("parent", "")
            }
            llm_payload.append(payload_item)
        
        batches.append(llm_payload)
    
    # Process batches
    categorized_entries = []
    for batch_idx, batch in enumerate(batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")
        
        try:
            llm_results = await llm_client.categorize_batch(batch)
            
            # Merge LLM results with original entries
            for llm_item in llm_results:
                original_entry = next(
                    (e for e in entries if e.get("id") == llm_item["id"]),
                    None
                )
                if original_entry:
                    merged = {
                        **original_entry,
                        "folder": llm_item.get("folder", "Unsorted"),
                        "tags": llm_item.get("tags", []),
                        "confidence": float(llm_item.get("confidence", 0.5))
                    }
                    categorized_entries.append(merged)
        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error processing batch {batch_idx}: {type(e).__name__}: {str(e)}")
            logger.debug(f"Full traceback:\n{error_details}")
            print(f"[ERROR] Batch {batch_idx} failed: {type(e).__name__}: {str(e)}")
            
            # Add entries as unsorted if LLM fails
            for item in batch:
                original_entry = next(
                    (e for e in entries if e.get("id") == item["id"]),
                    None
                )
                if original_entry:
                    categorized_entries.append({
                        **original_entry,
                        "folder": original_entry.get("parent", "Unsorted"),
                        "tags": [],
                        "confidence": 0.0
                    })
    
    # Return categorized entries directly - LLM already assigned folder names
    return categorized_entries

def build_folders(
    entries: List[Dict[str, Any]],
    max_folder_size: int = 6,
    min_confidence: float = 0.4,
    use_llm: bool = True
) -> List[Dict[str, Any]]:
    """Organize entries into folders with splitting logic"""
    
    if not use_llm:
        # Basic folder structure without LLM
        for entry in entries:
            entry["folder"] = entry.get("parent", "Unsorted")
        return entries
    
    # Group by folder name (already assigned by LLM)
    groups = defaultdict(list)
    for entry in entries:
        folder = entry.get("folder", "Unsorted")
        groups[folder].append(entry)
    
    # Process each group
    organized_entries = []
    for folder_name, items in groups.items():
        if len(items) <= max_folder_size:
            # Group fits in one folder - keep as is
            organized_entries.extend(items)
        else:
            # Need to split large folders
            split_groups = _split_large_group(items, max_folder_size)
            
            for i, subgroup in enumerate(split_groups):
                new_folder_name = folder_name
                if len(split_groups) > 1:
                    new_folder_name = f"{folder_name} ({i+1})"
                
                for item in subgroup:
                    item["folder"] = new_folder_name
                organized_entries.extend(subgroup)
    
    # Handle low confidence items
    final_entries = []
    unsorted_items = []
    
    for entry in organized_entries:
        if entry.get("confidence", 0) < min_confidence:
            entry["folder"] = "Unsorted"
            unsorted_items.append(entry)
        else:
            final_entries.append(entry)
    
    # Add unsorted items
    final_entries.extend(unsorted_items)
    
    return final_entries

def _split_large_group(
    items: List[Dict[str, Any]],
    max_size: int
) -> List[List[Dict[str, Any]]]:
    """Split large group into subgroups by domain or tags"""
    
    # Try to split by domain first
    domain_groups = defaultdict(list)
    for item in items:
        domain = item.get("domain", "unknown")
        if not domain or domain == "unknown":
            # Try to extract domain from URL
            url = item.get("url", "")
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                except:
                    domain = "unknown"
        domain_groups[domain].append(item)
    
    # If domain groups are small enough, use them
    subgroups = []
    for domain, domain_items in domain_groups.items():
        if len(domain_items) <= max_size:
            subgroups.append(domain_items)
        else:
            # Still too large, split by tags
            tag_groups = defaultdict(list)
            for item in domain_items:
                tags = item.get("tags", [])
                primary_tag = tags[0] if tags else "misc"
                tag_groups[primary_tag].append(item)
            
            # If tag groups still too large, create numeric shards
            for tag, tag_items in tag_groups.items():
                if len(tag_items) <= max_size:
                    subgroups.append(tag_items)
                else:
                    # Create numeric shards
                    for i in range(0, len(tag_items), max_size):
                        shard = tag_items[i:i + max_size]
                        subgroups.append(shard)
    
    return subgroups