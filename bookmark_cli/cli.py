# bookmark-cli/bookmark_cli/cli.py
import typer
from typing import Optional, List
import json
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
import asyncio

from .config import settings, init_config
from .loader import load_chrome_bookmarks, flatten_bookmarks
from .normalizer import normalize_url, deduplicate_entries
from .fetcher import MetadataFetcher
from .llm_client import LLMClient
from .categorizer import categorize_bookmarks, build_folders
from .preview import generate_preview, show_preview
from .exporter import export_to_chrome_format
from .storage import CacheStorage

app = typer.Typer(help="Organize Chrome bookmarks with LLM assistance")
console = Console()

@app.command()
def init(
    config_dir: Optional[Path] = typer.Option(
        None, help="Directory for config file"
    )
):
    """Initialize configuration"""
    config_path = init_config(config_dir)
    console.print(f"[green]✓ Configuration initialized at: {config_path}[/green]")

@app.command()
def import_bookmarks(
    input_file: Path = typer.Argument(..., help="Path to Chrome Bookmarks file (HTML or JSON)"),
    output_file: Path = typer.Option(
        Path("bookmarks_raw.json"), help="Output file for raw bookmarks"
    )
):
    """Import and flatten Chrome bookmarks (supports HTML and JSON)"""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    try:
        # Detect format based on extension or content
        if input_file.suffix.lower() in ['.html', '.htm']:
            from .loader import load_chrome_bookmarks_html
            console.print("[blue]Detected HTML format[/blue]")
            bookmarks = load_chrome_bookmarks_html(input_file)
            flattened = bookmarks  # HTML loader already flattens
        else:
            console.print("[blue]Detected JSON format[/blue]")
            bookmarks = load_chrome_bookmarks(input_file)
            flattened = flatten_bookmarks(bookmarks)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(flattened, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓ Imported {len(flattened)} bookmarks to {output_file}[/green]")
        
        # Show quick stats
        console.print(f"\n[bold]Quick stats:[/bold]")
        console.print(f"  Total bookmarks: {len(flattened)}")
        folders = set(b.get('parent', 'Unknown') for b in flattened)
        console.print(f"  Folders: {len(folders)}")
        
    except Exception as e:
        console.print(f"[red]Error importing bookmarks: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def clean(
    input_file: Path = typer.Option(
        Path("bookmarks_raw.json"), help="Input file with raw bookmarks"
    ),
    output_file: Path = typer.Option(
        Path("bookmarks_cleaned.json"), help="Output file for cleaned bookmarks"
    ),
    log_file: Path = typer.Option(
        Path("cleaned_tabs.log"), help="Log file for removed duplicates"
    )
):
    """Normalize URLs and remove duplicates"""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        deduped_entries, removed_entries = deduplicate_entries(entries)
        
        # Save cleaned bookmarks
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(deduped_entries, f, indent=2, ensure_ascii=False)
        
        # Save removal log
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("removed_id,removed_url,kept_id,kept_url,date_added_removed,date_added_kept\n")
            for removed, kept in removed_entries:
                f.write(f"{removed['id']},{removed['url']},{kept['id']},{kept['url']},{removed['date_added']},{kept['date_added']}\n")
        
        console.print(f"[green]✓ Cleaned {len(deduped_entries)} bookmarks, removed {len(removed_entries)} duplicates[/green]")
    except Exception as e:
        console.print(f"[red]Error cleaning bookmarks: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def categorize(
    input_file: Path = typer.Option(
        None, help="Input file with cleaned bookmarks"
    ),
    use_llm: bool = typer.Option(True, help="Use LLM for categorization"),
    model_name: str = typer.Option(
        None, help="Specific model to use (default: gemini-1.5-flash)"
    ),
    batch_size: int = typer.Option(50, help="Batch size for LLM calls"),
    concurrency: int = typer.Option(10, help="HTTP concurrency for fetching"),
    respect_robots: bool = typer.Option(True, help="Respect robots.txt"),
    skip_fetch: bool = typer.Option(False, help="Skip metadata fetching"),
    save_progress: bool = typer.Option(True, help="Save progress after each batch")
):
    """Fetch metadata and categorize bookmarks"""
    import signal
    import sys
    
    # Setup graceful shutdown
    shutdown_requested = False
    partial_results = []
    
    def signal_handler(sig, frame):
        nonlocal shutdown_requested
        console.print("\n[yellow]⚠ Shutdown requested. Saving progress...[/yellow]")
        shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Try multiple default file locations
    if input_file is None:
        for default_file in [Path("bookmarks_cleaned.json"), Path("bookmarks.json"), Path("bookmarks_raw.json")]:
            if default_file.exists():
                input_file = default_file
                console.print(f"[blue]Using: {input_file}[/blue]")
                break
    
    if input_file is None or not input_file.exists():
        console.print(f"[red]Error: No bookmark file found. Tried: bookmarks_cleaned.json, bookmarks.json, bookmarks_raw.json[/red]")
        console.print("[yellow]Run 'bookmark-cli import-bookmarks <chrome-bookmarks-file>' first[/yellow]")
        raise typer.Exit(1)
    
    output_file = Path("bookmarks_categorized.json")
    progress_file = Path("bookmarks_categorized.progress.json")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        console.print(f"[blue]Total bookmarks to process: {len(entries)}[/blue]")
        
        # Fetch metadata
        if not skip_fetch:
            console.print("[yellow]Fetching metadata...[/yellow]")
            try:
                fetcher = MetadataFetcher(
                    concurrency_limit=concurrency,
                    respect_robots=respect_robots
                )
                entries_with_meta = asyncio.run(fetcher.fetch_metadata(entries))
                console.print(f"[green]✓ Metadata fetched[/green]")
            except KeyboardInterrupt:
                console.print("\n[yellow]Metadata fetching interrupted[/yellow]")
                entries_with_meta = entries
            except Exception as e:
                console.print(f"[yellow]⚠ Metadata fetch error: {e}. Continuing with basic data...[/yellow]")
                entries_with_meta = entries
        else:
            entries_with_meta = entries
        
        # Categorize with LLM
        if use_llm and not shutdown_requested:
            console.print("[yellow]Categorizing with LLM...[/yellow]")
            
            # Determine model and API key
            model = model_name or settings.llm_model
            api_key = settings.gemini_api_key or settings.llm_api_key
            
            if not api_key:
                console.print("[red]Error: Gemini API key not found![/red]")
                console.print("[yellow]Set GEMINI_API_KEY in your .env file[/yellow]")
                console.print("[dim]Get a free API key at: https://makersuite.google.com/app/apikey[/dim]")
                raise typer.Exit(1)
            
            console.print(f"[blue]Using Gemini model: {model}[/blue]")
            console.print(f"[dim]Batch size: {batch_size} | Press Ctrl+C to stop gracefully[/dim]")
            
            try:
                llm_client = LLMClient(
                    api_key=api_key,
                    provider=settings.llm_provider,
                    model=model
                )
                
                categorized = asyncio.run(categorize_bookmarks(
                    entries_with_meta,
                    llm_client,
                    batch_size=batch_size
                ))
                
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠ Categorization interrupted by user[/yellow]")
                # Save whatever we have so far
                if progress_file.exists():
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        categorized = json.load(f)
                    console.print(f"[blue]Loaded {len(categorized)} bookmarks from progress file[/blue]")
                else:
                    categorized = entries_with_meta
                    console.print("[yellow]No progress file found, saving uncategorized data[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]✗ Error during categorization: {e}[/red]")
                console.print(f"[yellow]Check logs for details. Saving progress...[/yellow]")
                # Try to load progress
                if progress_file.exists():
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        categorized = json.load(f)
                    console.print(f"[blue]Recovered {len(categorized)} bookmarks from progress[/blue]")
                else:
                    categorized = entries_with_meta
                    console.print("[yellow]Saving with basic categorization[/yellow]")
        else:
            # Basic categorization without LLM
            console.print("[blue]Using basic categorization (no LLM)[/blue]")
            categorized = build_folders(entries_with_meta, use_llm=False)
        
        # Save categorized bookmarks
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(categorized, f, indent=2, ensure_ascii=False)
        
        # Clean up progress file
        if progress_file.exists():
            progress_file.unlink()
        
        console.print(f"\n[green]✓ Successfully processed {len(categorized)} bookmarks[/green]")
        console.print(f"[blue]Saved to: {output_file}[/blue]")
        console.print(f"[dim]Run 'bookmark-cli stats' to see details[/dim]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]✗ Fatal error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

@app.command()
def preview():
    """Show preview of categorized bookmarks"""
    try:
        input_file = Path("bookmarks_categorized.json")
        if not input_file.exists():
            console.print("[red]Error: Categorized bookmarks not found. Run 'categorize' first.[/red]")
            raise typer.Exit(1)
        
        with open(input_file, 'r', encoding='utf-8') as f:
            categorized = json.load(f)
        
        preview_data = generate_preview(categorized)
        confirmed = show_preview(preview_data, console)
        
        if confirmed:
            console.print("[green]✓ Preview confirmed[/green]")
        else:
            console.print("[yellow]Preview rejected[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error generating preview: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def export(
    output_file: Path = typer.Argument(
        Path("output.html"), help="Output file path (HTML or JSON)"
    ),
    original_file: Optional[Path] = typer.Option(
        None, help="Original Chrome bookmarks file for reference"
    )
):
    """Export organized bookmarks to Chrome format (HTML or JSON)"""
    try:
        input_file = Path("bookmarks_categorized.json")
        if not input_file.exists():
            console.print("[red]Error: Categorized bookmarks not found. Run 'categorize' first.[/red]")
            raise typer.Exit(1)
        
        with open(input_file, 'r', encoding='utf-8') as f:
            categorized = json.load(f)
        
        # Detect output format
        if output_file.suffix.lower() in ['.html', '.htm']:
            from .exporter import export_to_chrome_html
            console.print("[blue]Exporting to HTML format[/blue]")
            html_content = export_to_chrome_html(categorized)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
        else:
            console.print("[blue]Exporting to JSON format[/blue]")
            # Load original for structure if provided
            original = None
            if original_file and original_file.exists():
                with open(original_file, 'r', encoding='utf-8') as f:
                    original = json.load(f)
            
            exported = export_to_chrome_format(categorized, original_structure=original)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(exported, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓ Exported to {output_file}[/green]")
        console.print(f"[blue]Total bookmarks exported: {len(categorized)}[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error exporting bookmarks: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def list_items(
    folder: Optional[str] = typer.Option(None, help="Filter by folder name"),
    limit: int = typer.Option(20, help="Maximum items to show")
):
    """List bookmarks with their categorization"""
    try:
        input_file = Path("bookmarks_categorized.json")
        if not input_file.exists():
            console.print("[red]Error: Categorized bookmarks not found[/red]")
            raise typer.Exit(1)
        
        with open(input_file, 'r', encoding='utf-8') as f:
            categorized = json.load(f)
        
        table = Table(title="Bookmarks")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("URL", style="blue")
        table.add_column("Folder", style="green")
        table.add_column("Tags", style="yellow")
        
        count = 0
        for item in categorized:
            if folder and folder.lower() not in item.get('folder', '').lower():
                continue
            
            table.add_row(
                item.get('id', '')[:8],
                item.get('title', '')[:30],
                item.get('url', '')[:40],
                item.get('folder', 'Unsorted'),
                ', '.join(item.get('tags', [])[:3])
            )
            count += 1
            if count >= limit:
                break
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing bookmarks: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def stats(
    input_file: Path = typer.Option(
        None, help="Input file (defaults to latest available)"
    )
):
    """Show detailed statistics about bookmarks"""
    try:
        # Find the most recent file if not specified
        if input_file is None:
            for default_file in [Path("bookmarks_categorized.json"), Path("bookmarks_cleaned.json"), 
                                Path("bookmarks_raw.json"), Path("bookmarks.json")]:
                if default_file.exists():
                    input_file = default_file
                    break
        
        if input_file is None or not input_file.exists():
            console.print("[red]Error: No bookmark file found[/red]")
            raise typer.Exit(1)
        
        console.print(f"[blue]Analyzing: {input_file}[/blue]\n")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            bookmarks = json.load(f)
        
        # Calculate comprehensive statistics
        total = len(bookmarks)
        folders = {}
        tags = {}
        domains = {}
        protocols = {}
        has_description = 0
        has_keywords = 0
        fetch_errors = 0
        
        from urllib.parse import urlparse
        from datetime import datetime
        
        dates = []
        
        for item in bookmarks:
            # Folders
            folder = item.get('folder', item.get('parent', 'Unsorted'))
            folders[folder] = folders.get(folder, 0) + 1
            
            # Tags
            for tag in item.get('tags', []):
                tags[tag] = tags.get(tag, 0) + 1
            
            # Domains and protocols
            url = item.get('url', '')
            if url:
                parsed = urlparse(url)
                domain = parsed.netloc
                if domain:
                    domains[domain] = domains.get(domain, 0) + 1
                protocols[parsed.scheme] = protocols.get(parsed.scheme, 0) + 1
            
            # Metadata stats
            if item.get('description'):
                has_description += 1
            if item.get('keywords'):
                has_keywords += 1
            if item.get('fetch_error'):
                fetch_errors += 1
            
            # Date tracking
            if item.get('date_added'):
                try:
                    dates.append(int(item['date_added']))
                except:
                    pass
        
        # Display statistics
        console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]       BOOKMARK STATISTICS[/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
        
        console.print(f"[bold]📊 Overview:[/bold]")
        console.print(f"  Total bookmarks: [green]{total}[/green]")
        console.print(f"  Unique folders: [yellow]{len(folders)}[/yellow]")
        console.print(f"  Unique domains: [blue]{len(domains)}[/blue]")
        console.print(f"  Unique tags: [magenta]{len(tags)}[/magenta]")
        
        if has_description or has_keywords or fetch_errors:
            console.print(f"\n[bold]📝 Metadata:[/bold]")
            console.print(f"  With descriptions: {has_description} ({has_description*100//total if total else 0}%)")
            console.print(f"  With keywords: {has_keywords} ({has_keywords*100//total if total else 0}%)")
            if fetch_errors:
                console.print(f"  Fetch errors: [red]{fetch_errors}[/red]")
        
        console.print(f"\n[bold]🌐 Protocols:[/bold]")
        for protocol, count in sorted(protocols.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {protocol}: {count}")
        
        console.print(f"\n[bold]📁 Top 10 Folders:[/bold]")
        for folder, count in sorted(folders.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = count * 100 / total
            console.print(f"  {folder[:40]:40} : {count:4} ({percentage:.1f}%)")
        
        if tags:
            console.print(f"\n[bold]🏷️  Top 10 Tags:[/bold]")
            for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]:
                console.print(f"  {tag[:40]:40} : {count:4}")
        
        console.print(f"\n[bold]🌍 Top 10 Domains:[/bold]")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
            console.print(f"  {domain[:40]:40} : {count:4}")
        
        # Date analysis
        if dates:
            dates_sorted = sorted(dates)
            oldest = datetime.fromtimestamp(dates_sorted[0] / 1000000)
            newest = datetime.fromtimestamp(dates_sorted[-1] / 1000000)
            console.print(f"\n[bold]📅 Date Range:[/bold]")
            console.print(f"  Oldest bookmark: {oldest.strftime('%Y-%m-%d')}")
            console.print(f"  Newest bookmark: {newest.strftime('%Y-%m-%d')}")
        
        console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
        
    except Exception as e:
        console.print(f"[red]Error calculating statistics: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()