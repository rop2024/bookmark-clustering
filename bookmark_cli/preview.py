# bookmark-cli/bookmark_cli/preview.py
import json
from typing import Dict, List, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from collections import defaultdict, Counter

def generate_preview(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate preview data for categorized bookmarks"""
    
    # Calculate statistics
    total = len(entries)
    
    folders = defaultdict(list)
    tags_counter = Counter()
    domain_counter = Counter()
    
    for entry in entries:
        folder = entry.get("folder", "Unsorted")
        folders[folder].append(entry)
        
        for tag in entry.get("extra_tags", []):
            tags_counter[tag] += 1
        
        domain = entry.get("domain", "")
        if domain:
            domain_counter[domain] += 1
    
    # Calculate folder coherence scores
    folder_stats = {}
    for folder_name, folder_items in folders.items():
        if folder_items:
            confidences = [item.get("confidence", 0) for item in folder_items]
            avg_confidence = sum(confidences) / len(confidences)
            
            # Check if items share domain
            domains = [item.get("domain") for item in folder_items]
            unique_domains = len(set(d for d in domains if d))
            domain_coherence = 1 - (unique_domains / max(len(domains), 1))
            
            folder_stats[folder_name] = {
                "count": len(folder_items),
                "avg_confidence": round(avg_confidence, 2),
                "domain_coherence": round(domain_coherence, 2),
                "items": folder_items[:10]  # Preview first 10 items
            }
    
    # Get top tags
    top_tags = tags_counter.most_common(10)
    
    # Get domain distribution
    top_domains = domain_counter.most_common(10)
    
    # Compare with original folders if available
    original_folders = defaultdict(int)
    for entry in entries:
        original_folder = entry.get("parent", "Unknown")
        original_folders[original_folder] += 1
    
    return {
        "total_bookmarks": total,
        "folders": folder_stats,
        "top_tags": top_tags,
        "top_domains": top_domains,
        "original_folders": dict(original_folders),
        "broken_count": len([e for e in entries if e.get("primary_tag") == "broken"]),
        "unsorted_count": len([e for e in entries if e.get("folder") == "Unsorted"])
    }

def show_preview(preview_data: Dict[str, Any], console: Console) -> bool:
    """Display preview and ask for confirmation"""
    
    console.clear()
    console.print(Panel.fit("[bold cyan]Bookmark Organizer Preview[/bold cyan]"))
    
    # Summary statistics
    console.print("\n[bold]Summary Statistics:[/bold]")
    console.print(f"Total bookmarks: {preview_data['total_bookmarks']}")
    console.print(f"Folders created: {len(preview_data['folders'])}")
    console.print(f"Broken links: {preview_data['broken_count']}")
    console.print(f"Unsorted items: {preview_data['unsorted_count']}")
    
    # Folder preview
    console.print("\n[bold]Folder Structure:[/bold]")
    folder_table = Table(show_header=True, header_style="bold magenta")
    folder_table.add_column("Folder", style="cyan")
    folder_table.add_column("Count", style="green")
    folder_table.add_column("Avg Confidence", style="yellow")
    folder_table.add_column("Domain Coherence", style="blue")
    
    for folder_name, stats in preview_data["folders"].items():
        folder_table.add_row(
            folder_name[:30],
            str(stats["count"]),
            f"{stats['avg_confidence']:.2f}",
            f"{stats['domain_coherence']:.2f}"
        )
    
    console.print(folder_table)
    
    # Top tags
    console.print("\n[bold]Top 10 Tags:[/bold]")
    tags_table = Table(show_header=True, header_style="bold magenta")
    tags_table.add_column("Tag", style="cyan")
    tags_table.add_column("Count", style="green")
    
    for tag, count in preview_data["top_tags"]:
        tags_table.add_row(tag, str(count))
    
    console.print(tags_table)
    
    # Sample items from first folder
    first_folder = next(iter(preview_data["folders"].values()), None)
    if first_folder and first_folder["items"]:
        console.print("\n[bold]Sample Items (first folder):[/bold]")
        for i, item in enumerate(first_folder["items"][:5], 1):
            title = item.get("title", "No title")[:50]
            url = item.get("url", "No URL")[:40]
            console.print(f"  {i}. {title}")
            console.print(f"     [blue]{url}[/blue]")
    
    # Ask for confirmation
    console.print("\n" + "="*50)
    response = input("\nDo you want to proceed with this organization? (y/N): ")
    
    # Save preview data
    with open("preview.diff", "w") as f:
        json.dump(preview_data, f, indent=2)
    
    return response.lower() in ["y", "yes"]