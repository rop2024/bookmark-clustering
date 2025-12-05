# Bookmark CLI - Architecture Documentation

## **Overview**

Bookmark CLI is a Python-based command-line tool designed to organize and categorize Chrome bookmarks using Large Language Models (LLMs). It supports both cloud-based APIs and local LLMs via Ollama for privacy-conscious users.

## **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│                    (bookmark_cli/cli.py)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ├──> Config Management (config.py)
                       │    └─> .env file, Pydantic Settings
                       │
                       ├──> Import Pipeline
                       │    ├─> Loader (loader.py)
                       │    ├─> Normalizer (normalizer.py)
                       │    └─> Fetcher (fetcher.py)
                       │
                       ├──> LLM Processing
                       │    ├─> LLM Client (llm_client.py)
                       │    │   ├─> Cloud Provider API
                       │    │   └─> Ollama Wrapper (ollama_wrapper.py)
                       │    └─> Categorizer (categorizer.py)
                       │
                       ├──> Output & Export
                       │    ├─> Preview (preview.py)
                       │    └─> Exporter (exporter.py)
                       │
                       └──> Storage & Caching
                            └─> Cache Storage (storage.py)
```

## **Component Architecture**

### **1. CLI Layer (`cli.py`)**

**Purpose**: Command-line interface and workflow orchestration

**Main Framework**: Typer (CLI builder) + Rich (console formatting)

**Key Commands**:

1. **`import [file_path]`**
   - **Input**: Path to Chrome bookmarks file (JSON or HTML)
   - **Processing**:
     1. Detect file format (JSON vs HTML)
     2. Call appropriate loader (`load_chrome_bookmarks` or `load_chrome_bookmarks_html`)
     3. Flatten bookmark structure
     4. Save to `bookmarks_raw.json`
   - **Output**: Console message with bookmark count, saved JSON file
   - **Example**: `bookmark-cli import bookmarks.html`

2. **`clean`**
   - **Input**: Reads `bookmarks_raw.json`
   - **Processing**:
     1. Load raw bookmarks
     2. Normalize URLs with `normalize_url()`
     3. Deduplicate with `deduplicate_entries()`
     4. Log removed duplicates to `cleaned_tabs.log`
     5. Save to `bookmarks_cleaned.json`
   - **Output**: Console message with deduplication stats, cleaned JSON file
   - **Example**: `bookmark-cli clean`

3. **`categorize [options]`**
   - **Input**: Reads `bookmarks_cleaned.json`
   - **Options**:
     - `--use-llm / --no-use-llm`: Enable LLM categorization (default: enabled)
     - `--model-name TEXT`: Model to use (default: gemini-2.5-flash)
     - `--batch-size INT`: Bookmarks per API call (default: 50)
     - `--concurrency INT`: Parallel metadata fetches (default: 10)
     - `--skip-fetch`: Skip metadata fetching
     - `--save-progress`: Save after each batch (default: enabled)
   - **Processing**:
     1. Load cleaned bookmarks
     2. Fetch metadata with `MetadataFetcher.fetch_all()`
     3. Batch bookmarks (chunks of batch_size)
     4. For each batch:
        - Call `LLMClient.categorize_batch()`
        - Save progress to `.categorization_progress.json`
        - Display progress bar
     5. Handle Ctrl+C gracefully (saves progress)
     6. Save final result to `bookmarks_categorized.json`
   - **Output**: Console progress, categorized JSON file
   - **Example**: `bookmark-cli categorize --batch-size 50`

4. **`stats`**
   - **Input**: Reads `bookmarks_categorized.json`
   - **Processing**:
     1. Load categorized bookmarks
     2. Calculate statistics:
        - Total bookmarks
        - Number of folders
        - Folder distribution (bookmarks per folder)
        - Tag frequency
        - Uncategorized count
     3. Format with Rich tables
   - **Output**: Console display with statistics tables
   - **Example**: `bookmark-cli stats`

5. **`export [output_file]`**
   - **Input**: 
     - Reads `bookmarks_categorized.json`
     - `output_file`: Target HTML path (default: `organized_bookmarks.html`)
   - **Processing**:
     1. Load categorized bookmarks
     2. Build folder hierarchy
     3. Generate Netscape HTML format
     4. Write to output file
   - **Output**: HTML file for Chrome import
   - **Example**: `bookmark-cli export organized.html`

**Signal Handling** (Graceful Shutdown):
- Catches `SIGINT` (Ctrl+C) and `SIGTERM`
- Sets `shutdown_requested` flag
- Completes current batch before stopping
- Saves progress to `.categorization_progress.json`
- Allows resuming from last successful batch

**Progress Recovery**:
- Progress file: `.categorization_progress.json`
- Structure:
  ```json
  {
    "last_batch": 3,
    "total_batches": 7,
    "categorized_bookmarks": [...],
    "timestamp": "2025-12-04T15:30:00"
  }
  ```
- On restart: Resumes from `last_batch + 1`

**Technology**: Typer (CLI framework), Rich (console output), signal (graceful shutdown)

---

### **2. Configuration Management (`config.py`)**

**Purpose**: Centralized settings management with environment variables

**Main Class**: `Settings` (Pydantic BaseSettings)

**Key Features**:
- Pydantic-based settings validation with type checking
- Environment variable loading via `.env` file
- Support for multiple LLM providers
- Default values for all settings

**Settings Structure**:
```python
class Settings(BaseSettings):
    # LLM Configuration
    llm_provider: str = "gemini"               # Provider: gemini, openai, anthropic
    llm_api_key: Optional[str] = None          # General API key
    llm_model: str = "gemini-2.5-flash"        # Model identifier
    llm_base_url: Optional[str] = None         # Custom API endpoint
    gemini_api_key: Optional[str] = None       # Gemini-specific key
    
    # Fetch Configuration
    fetch_concurrency: int = 10                # Parallel HTTP requests
    respect_robots: bool = True                # Honor robots.txt
    timeout_seconds: int = 30                  # HTTP timeout
    
    # Categorization Configuration
    batch_size: int = 50                       # Bookmarks per LLM call
    max_folder_size: int = 6                   # Max items before folder split
    min_confidence: float = 0.4                # Minimum categorization confidence
    
    # Cache Configuration
    cache_enabled: bool = True                 # Enable metadata cache
    cache_path: Path = Path(".bookmark_cache") # Cache directory
    
    # Export Configuration
    preserve_original_ids: bool = True         # Keep Chrome bookmark IDs
    add_metadata_comments: bool = True         # Add comments to HTML
    
    class Config:
        env_file = ".env"                      # Load from .env
        extra = "ignore"                       # Ignore unknown env vars
```

**Environment Variable Loading**:
1. Reads `.env` file in project root
2. Maps env vars to settings fields (case-insensitive)
3. Example `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.5-flash
   BATCH_SIZE=50
   FETCH_CONCURRENCY=10
   ```

**Settings Instance**:
```python
settings = Settings()  # Global singleton
# Access anywhere: settings.llm_api_key
```

**Additional Functions**:

1. **`init_config(config_dir: Path) -> Path`**
   - **Input**: Optional config directory path
   - **Processing**:
     1. Create config directory if not exists (default: `~/.config/bookmark-cli`)
     2. Create `config.json` with default values
     3. Return config file path
   - **Output**: Path to config file
   - **Default Config**:
     ```json
     {
       "llm_provider": "gemini",
       "llm_model": "gemini-2.5-flash",
       "fetch_concurrency": 10,
       "respect_robots": true,
       "batch_size": 50,
       "max_folder_size": 6
     }
     ```

**Type Validation**:
- Pydantic validates types at runtime
- Invalid values raise `ValidationError`
- Example: `batch_size` must be positive integer

**Technology**: Pydantic v2, pydantic-settings, python-dotenv

---

### **3. Import Pipeline**

#### **3.1 Loader (`loader.py`)**

**Purpose**: Load and flatten Chrome bookmarks from JSON or HTML formats

**Key Functions**:

1. **`load_chrome_bookmarks(file_path: str) -> List[Dict]`**
   - **Input**: Path to Chrome Bookmarks file (JSON format)
   - **Processing**:
     - Reads JSON file structure
     - Recursively traverses nested bookmark folders
     - Extracts bookmark properties: `name`, `url`, `date_added`, `guid`
     - Flattens hierarchical structure into linear list
   - **Output**: List of dictionaries, each containing:
     ```python
     {
       "title": str,
       "url": str,
       "date_added": int,  # Unix timestamp in microseconds
       "id": str,          # Chrome GUID
       "folder": str       # Original folder path
     }
     ```

2. **`load_chrome_bookmarks_html(file_path: str) -> List[Dict]`**
   - **Input**: Path to exported Chrome HTML bookmarks file
   - **Processing**:
     - Parses Netscape bookmark HTML format with BeautifulSoup4
     - Finds all `<A>` anchor tags containing bookmarks
     - Extracts attributes: `HREF`, `ADD_DATE`, `ICON`
     - Identifies parent folder by searching backward for `<H3>` tags
     - Converts ADD_DATE from Unix seconds to Chrome microseconds format
   - **Output**: Same structure as JSON loader
   - **Example HTML Structure**:
     ```html
     <DT><H3>Development</H3>
     <DL><p>
       <DT><A HREF="https://github.com" ADD_DATE="1234567890">GitHub</A>
     </DL><p>
     ```

3. **`flatten_bookmarks(bookmark_tree: Dict) -> List[Dict]`**
   - **Input**: Nested bookmark tree from Chrome JSON
   - **Processing**:
     - Recursive depth-first traversal
     - Tracks folder path during traversal
     - Filters out folder nodes, keeps only URLs
   - **Output**: Flat list of bookmarks with folder paths preserved

#### **3.2 Normalizer (`normalizer.py`)**

**Purpose**: URL normalization and deduplication to remove duplicates

**Key Functions**:

1. **`normalize_url(url: str) -> str`**
   - **Input**: Raw URL string (may have inconsistent format)
   - **Processing Steps**:
     1. Parse URL into components using `urllib.parse.urlparse()`
     2. Convert scheme to lowercase (`HTTP` → `http`)
     3. Convert hostname to lowercase (`GitHub.com` → `github.com`)
     4. Remove default ports (`https://site.com:443` → `https://site.com`)
     5. Remove trailing slashes (`/path/` → `/path`)
     6. Sort query parameters alphabetically for consistency
     7. Preserve URL fragments (`#section`)
     8. Extract domain with `tldextract` for better matching
   - **Output**: Canonical URL string
   - **Example**:
     ```python
     normalize_url("HTTPS://GitHub.COM:443/user/repo/")
     # Returns: "https://github.com/user/repo"
     ```

2. **`deduplicate_entries(bookmarks: List[Dict]) -> Tuple[List[Dict], List[Dict]]`**
   - **Input**: List of bookmark dictionaries
   - **Processing**:
     1. Normalize each bookmark's URL
     2. Group bookmarks by normalized URL (dictionary keyed by URL)
     3. For duplicates, keep the **oldest** entry by `date_added` timestamp
     4. Collect removed entries for logging
     5. Generate deduplication report
   - **Output**: Tuple of `(unique_bookmarks, removed_bookmarks)`
   - **Deduplication Logic**:
     ```python
     seen_urls = {}
     for bookmark in bookmarks:
         normalized = normalize_url(bookmark['url'])
         if normalized not in seen_urls:
             seen_urls[normalized] = bookmark
         elif bookmark['date_added'] < seen_urls[normalized]['date_added']:
             # Keep older bookmark
             removed.append(seen_urls[normalized])
             seen_urls[normalized] = bookmark
         else:
             removed.append(bookmark)
     ```

3. **`log_removed_entries(removed: List[Dict], log_file: str)`**
   - **Input**: List of removed duplicates, path to CSV log
   - **Processing**:
     - Writes CSV with columns: `title`, `url`, `date_added`, `reason`
     - Formats timestamps as human-readable dates
   - **Output**: CSV file `cleaned_tabs.log`

**Technology**: `tldextract`, `urllib.parse`

#### **3.3 Fetcher (`fetcher.py`)**

**Purpose**: Asynchronous metadata fetching from bookmark URLs

**Main Class**: `MetadataFetcher`

**Key Methods**:

1. **`__init__(concurrency: int, timeout: int, respect_robots: bool)`**
   - **Input**: Configuration parameters
   - **Processing**:
     - Creates async HTTP client with connection pooling
     - Sets up semaphore for concurrency control
     - Initializes robots.txt parser (if enabled)
   - **Output**: Configured fetcher instance

2. **`fetch_all(bookmarks: List[Dict]) -> List[Dict]`**
   - **Input**: List of bookmarks with URLs
   - **Processing**:
     1. Creates async tasks for each URL
     2. Controls concurrency with asyncio.Semaphore (default: 10 parallel requests)
     3. Uses asyncio.gather() to execute all tasks concurrently
     4. Handles failures gracefully (continues on errors)
     5. Shows progress bar with Rich console
   - **Output**: Same bookmark list with added `metadata` field
   - **Concurrency Model**:
     ```python
     async with self.semaphore:  # Limit to N concurrent requests
         async with httpx.AsyncClient() as client:
             response = await client.get(url, timeout=30)
     ```

3. **`fetch_single(url: str) -> Dict`**
   - **Input**: Single URL string
   - **Processing Steps**:
     1. Check robots.txt (if enabled) - skip if disallowed
     2. Send HTTP GET request with timeout
     3. Parse HTML with BeautifulSoup4
     4. Extract metadata in priority order:
        - **Title**: `<meta property="og:title">` → `<title>` tag
        - **Description**: `<meta property="og:description">` → `<meta name="description">`
        - **Keywords**: `<meta name="keywords">`
        - **Content**: First 500 chars of visible text
        - **Image**: `<meta property="og:image">`
     5. Clean extracted text (strip whitespace, decode HTML entities)
     6. Apply retry logic with exponential backoff (3 attempts)
   - **Output**: Dictionary with metadata:
     ```python
     {
       "title": str,
       "description": str,
       "keywords": List[str],
       "content_preview": str,
       "image": str,
       "fetched_at": str,  # ISO timestamp
       "error": str | None
     }
     ```
   - **Error Handling**:
     - Timeout → Returns partial metadata with error flag
     - 404/403 → Returns error metadata
     - Network error → Retries 3 times with backoff

4. **`@retry` Decorator Configuration**:
   ```python
   @retry(
       stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
   )
   ```

**Technology**: `httpx` (async HTTP), `BeautifulSoup4` (HTML parsing), `tenacity` (retry logic)

**Configuration**:
- `concurrency_limit` - Max parallel requests (default: 10)
- `timeout` - Request timeout in seconds (default: 30)
- `respect_robots` - Honor robots.txt (default: True)

---

### **4. LLM Processing**

#### **4.1 LLM Client (`llm_client.py`)**

**Purpose**: Unified interface for LLM providers with bookmark categorization logic

**Main Class**: `LLMClient`

**Supported Providers**:
- Google Gemini (primary, via `gemini_client.py`)
- OpenAI (extensible)
- Anthropic (extensible)

**Key Methods**:

1. **`__init__(api_key: str, provider: str, model: str)`**
   - **Input**: 
     - `api_key`: API key for cloud provider
     - `provider`: Provider name (default: "gemini")
     - `model`: Model identifier (default: "gemini-2.5-flash")
   - **Processing**:
     - Instantiate provider-specific client (GeminiClient)
     - Store configuration
     - Validate API key presence
   - **Output**: Configured LLMClient instance

2. **`categorize_batch(bookmarks: List[Dict]) -> List[Dict]`**
   - **Input**: Batch of bookmarks with metadata
   - **Processing**:
     1. Build system prompt with categorization instructions
     2. Format bookmark data into user prompt:
        ```
        Categorize these bookmarks:
        
        1. Title: "GitHub"
           URL: "https://github.com"
           Description: "Code hosting platform"
        
        2. Title: "Stack Overflow"
           URL: "https://stackoverflow.com"
           Description: "Programming Q&A"
        ```
     3. Call `self.client.generate_json(user_prompt, system_prompt)`
     4. Parse JSON response
     5. Map results back to bookmarks by ID
     6. Handle parsing errors (fallback to uncategorized)
   - **Output**: List of categorization results:
     ```python
     [
       {"id": "1", "folder": "Development", "tags": ["git", "code"]},
       {"id": "2", "folder": "Programming", "tags": ["qa", "help"]}
     ]
     ```

3. **`_get_system_prompt() -> str`**
   - **Input**: None
   - **Processing**: Returns categorization instructions
   - **Output**: System prompt string:
     ```
     You are a bookmark organization assistant. Analyze the provided 
     bookmarks and assign each to a logical folder. Also suggest 
     relevant tags.
     
     Rules:
     - Create descriptive folder names (e.g., "Development", "News")
     - Keep folder names concise (2-3 words max)
     - Suggest 2-4 tags per bookmark
     - Return valid JSON array
     
     Response format:
     [
       {"id": "bookmark_id", "folder": "Category Name", "tags": ["tag1", "tag2"]}
     ]
     ```

4. **`_format_bookmarks_for_prompt(bookmarks: List[Dict]) -> str`**
   - **Input**: List of bookmarks
   - **Processing**:
     1. Enumerate bookmarks
     2. Format each with title, URL, description
     3. Include metadata if available
     4. Truncate long descriptions (max 200 chars)
   - **Output**: Formatted string for LLM prompt

**Architecture**:
```python
class LLMClient:
    def __init__(self, api_key, provider, model):
        if provider == "gemini":
            self.client = GeminiClient(api_key, model)
        elif provider == "openai":
            self.client = OpenAIClient(api_key, model)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def categorize_batch(self, bookmarks):
        system_prompt = self._get_system_prompt()
        user_prompt = self._format_bookmarks_for_prompt(bookmarks)
        result = await self.client.generate_json(user_prompt, system_prompt)
        return self._parse_categorization_result(result, bookmarks)
```

**Error Handling**:
- **API failures**: Retry with exponential backoff (3 attempts)
- **Invalid JSON**: Log error, assign to "Uncategorized"
- **Missing fields**: Use defaults (folder="Uncategorized", tags=[])
- **Rate limits**: Wait and retry with longer backoff

#### **4.2 Gemini Client (`gemini_client.py`)**

**Purpose**: Google Gemini API integration for cloud-based LLM

**Main Class**: `GeminiClient`

**Key Methods**:

1. **`__init__(api_key: str, model_name: str)`**
   - **Input**: 
     - `api_key`: Google Gemini API key
     - `model_name`: Model identifier (default: `gemini-2.5-flash`)
   - **Processing**:
     - Maps model names to API-compatible versions
     - Model mapping: `gemini-1.5-flash` → `gemini-2.5-flash`
     - Sets base URL: `https://generativelanguage.googleapis.com/v1beta/models`
   - **Output**: Configured client instance

2. **`async generate(prompt: str, system_prompt: str) -> str`**
   - **Input**: 
     - `prompt`: User query/request
     - `system_prompt`: Instruction context (combined with prompt)
   - **Processing**:
     1. Constructs API request URL with model and API key
     2. Builds payload with generation config:
        ```python
        {
          "contents": [{"parts": [{"text": system_prompt + prompt}]}],
          "generationConfig": {
            "temperature": 0.3,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json"
          }
        }
        ```
     3. Sends POST request with 120s timeout
     4. Extracts text from nested response structure:
        ```python
        result["candidates"][0]["content"]["parts"][0]["text"]
        ```
     5. Applies retry logic (3 attempts with exponential backoff)
   - **Output**: Generated text response (JSON string)
   - **Error Handling**: 
     - 404 → Model not found error
     - 429 → Rate limit exceeded
     - Timeout → Retries with backoff

3. **`async generate_json(prompt: str, system_prompt: str) -> Dict`**
   - **Input**: Same as `generate()`
   - **Processing**:
     1. Calls `generate()` to get response
     2. Attempts multiple JSON extraction methods:
        - Direct parse (if response starts with `{` or `[`)
        - Extract from markdown code blocks (```json ... ```)
        - Find JSON within response text
     3. Handles malformed JSON gracefully
   - **Output**: Parsed dictionary/list
   - **Fallback**: Returns empty list `[]` on parse failure

**Technology**: `httpx` (async HTTP), `tenacity` (retry logic), `json` (parsing)

**Configuration**:
- `api_key` - Gemini API key from environment
- `model` - Gemini model name (gemini-2.5-flash, gemini-2.5-pro)
- `base_url` - API endpoint (v1beta)

#### **4.3 Categorizer (`categorizer.py`)**

**Purpose**: Bookmark categorization using LLM with batch processing

**Key Functions**:

1. **`categorize_bookmarks(bookmarks: List[Dict], llm_client: LLMClient, batch_size: int) -> List[Dict]`**
   - **Input**: 
     - `bookmarks`: List of bookmarks with metadata
     - `llm_client`: Configured LLM client (Gemini)
     - `batch_size`: Number of bookmarks per API call (default: 50)
   - **Processing Pipeline**:
     1. **Batch Creation**: Split bookmarks into chunks of size `batch_size`
     2. **For each batch**:
        - Build categorization prompt with bookmark details
        - Call LLM via `llm_client.categorize_batch()`
        - Parse JSON response
        - Merge results back to original bookmarks
        - Save progress to `.categorization_progress.json`
     3. **Progress Tracking**: Display Rich progress bar with batch number
     4. **Error Recovery**: Continue with remaining batches on failure
   - **Output**: Original bookmark list with added fields:
     ```python
     {
       ...existing_fields,
       "folder": str,      # Assigned category
       "tags": List[str],  # Relevant tags
       "confidence": float # Categorization confidence (optional)
     }
     ```

2. **`build_folders(categorized_bookmarks: List[Dict]) -> Dict[str, List[Dict]]`**
   - **Input**: Bookmarks with `folder` assignments
   - **Processing**:
     1. Group bookmarks by `folder` name
     2. Count items per folder
     3. Split large folders (> `max_folder_size`) into subfolders
     4. Handle uncategorized items (assign to "Uncategorized" folder)
     5. Sort folders alphabetically
   - **Output**: Dictionary mapping folder names to bookmark lists:
     ```python
     {
       "Development": [bookmark1, bookmark2, ...],
       "News": [bookmark3, ...],
       "Uncategorized": [bookmark4, ...]
     }
     ```
   - **Folder Splitting Logic**:
     ```python
     if len(bookmarks_in_folder) > max_folder_size:
         # Split into subfolders by domain or tags
         subfolders = create_subfolders(bookmarks_in_folder)
     ```

**LLM Prompt Structure**:
```
System Prompt:
You are a bookmark organization assistant. Categorize bookmarks into 
logical folders and suggest relevant tags.

User Prompt:
Categorize these bookmarks:

1. Title: "Python Documentation"
   URL: "https://docs.python.org"
   Description: "Official Python documentation"

2. Title: "GitHub"
   URL: "https://github.com"
   Description: "Code hosting platform"

Return JSON array:
[
  {"id": "1", "folder": "Programming/Python", "tags": ["python", "docs"]},
  {"id": "2", "folder": "Development Tools", "tags": ["git", "code"]}
]
```

**Batch Processing Details**:
- **Batch size**: 50 for Gemini API (handles larger context)
- **Concurrency**: Sequential batches (avoids rate limits)
- **Progress saving**: After each batch to `.categorization_progress.json`
- **Resume capability**: Can restart from last successful batch
- **Error handling**: Failed batches skip to next, logged for manual review

**Response Parsing**:
1. Extract JSON from LLM response
2. Validate schema (id, folder, tags fields present)
3. Map results by bookmark ID
4. Fallback for invalid responses: assign to "Uncategorized"

**Performance**:
- 309 bookmarks ÷ 50 per batch = ~7 API calls
- Average time: 3-5 seconds per batch
- Total time: ~30-40 seconds for full categorization

---

### **5. Output & Export**

#### **5.1 Preview (`preview.py`)**

**Purpose**: Interactive preview and statistics of categorization results

**Key Functions**:

1. **`generate_preview(bookmarks: List[Dict]) -> Dict`**
   - **Input**: Categorized bookmarks
   - **Processing**:
     1. Count total bookmarks
     2. Count bookmarks per folder
     3. Extract and count all tags
     4. Calculate categorization rate (% with folders assigned)
     5. Identify most common tags
     6. Find largest folders
   - **Output**: Statistics dictionary:
     ```python
     {
       "total_bookmarks": int,
       "folders": Dict[str, int],  # Folder name → count
       "tags": Dict[str, int],     # Tag → frequency
       "uncategorized": int,
       "categorization_rate": float
     }
     ```

2. **`show_preview(stats: Dict, bookmarks: List[Dict])`**
   - **Input**: Statistics and bookmark list
   - **Processing**:
     1. Create Rich console for formatted output
     2. Generate summary table:
        - Total bookmarks
        - Number of folders
        - Categorization rate
     3. Create folder distribution table (sorted by count)
     4. Create top tags table (sorted by frequency)
     5. Show sample bookmarks from each folder (first 3)
   - **Output**: Formatted console display with Rich tables:
     ```
     ╭─ Categorization Summary ─╮
     │ Total Bookmarks:    309  │
     │ Folders Created:     15  │
     │ Categorization:   98.5%  │
     ╰──────────────────────────╯

     ╭─ Folder Distribution ─────────╮
     │ Development        45 items   │
     │ News               32 items   │
     │ Entertainment      28 items   │
     ╰───────────────────────────────╯
     ```

3. **`confirm_categorization() -> bool`**
   - **Input**: None (user prompt)
   - **Processing**:
     - Display preview
     - Prompt user: "Proceed with export? [y/N]"
     - Read user input
   - **Output**: Boolean (True = proceed, False = cancel)

**User Interaction Flow**:
1. System shows statistics and preview
2. User reviews folder organization
3. User confirms or rejects
4. If rejected → returns to CLI, can adjust settings
5. If confirmed → proceeds to export

#### **5.2 Exporter (`exporter.py`)**

**Purpose**: Export categorized bookmarks to Chrome-compatible HTML format

**Key Functions**:

1. **`export_to_chrome_html(bookmarks: List[Dict], output_path: str)`**
   - **Input**: 
     - `bookmarks`: Categorized bookmark list with folder assignments
     - `output_path`: Target file path for HTML output
   - **Processing**:
     1. **Group by folders**: Create dictionary of folder → bookmarks
     2. **Build HTML structure**: Generate Netscape Bookmark Format
        ```html
        <!DOCTYPE NETSCAPE-Bookmark-file-1>
        <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
        <TITLE>Bookmarks</TITLE>
        <H1>Bookmarks</H1>
        <DL><p>
        ```
     3. **For each folder**:
        - Create folder header: `<DT><H3>Folder Name</H3>`
        - Open folder list: `<DL><p>`
        - Add bookmarks as anchor tags with attributes
        - Close folder list: `</DL><p>`
     4. **Format bookmark entries**:
        ```html
        <DT><A HREF="url" 
               ADD_DATE="timestamp" 
               ICON="favicon_data">
          Title [tag1, tag2]
        </A>
        ```
     5. **Timestamp conversion**: Chrome microseconds → Unix seconds
     6. **HTML escaping**: Escape special characters in titles/URLs
     7. **Write file**: Save complete HTML structure
   - **Output**: HTML file compatible with Chrome bookmark import

2. **`build_folder_hierarchy(bookmarks: List[Dict]) -> Dict`**
   - **Input**: Flat bookmark list
   - **Processing**:
     1. Parse nested folder paths (e.g., "Development/Python")
     2. Create hierarchical structure
     3. Handle folder splitting for large folders
   - **Output**: Nested dictionary representing folder tree:
     ```python
     {
       "Development": {
         "Python": [bookmark1, bookmark2],
         "JavaScript": [bookmark3]
       },
       "News": [bookmark4, bookmark5]
     }
     ```

3. **`format_timestamp(chrome_timestamp: int) -> int`**
   - **Input**: Chrome timestamp (microseconds since 1601)
   - **Processing**: Convert to Unix timestamp (seconds since 1970)
   - **Output**: Integer Unix timestamp for HTML ADD_DATE attribute

**Output HTML Structure**:
```html
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
  <DT><H3 ADD_DATE="1701907200">Development</H3>
  <DL><p>
    <DT><A HREF="https://github.com" ADD_DATE="1701907200">
      GitHub [git, code, collaboration]
    </A>
    <DT><A HREF="https://stackoverflow.com" ADD_DATE="1701907300">
      Stack Overflow [programming, qa, community]
    </A>
  </DL><p>
  
  <DT><H3 ADD_DATE="1701907400">News</H3>
  <DL><p>
    <DT><A HREF="https://news.ycombinator.com" ADD_DATE="1701907400">
      Hacker News [tech, news]
    </A>
  </DL><p>
</DL><p>
```

**Chrome Import Process**:
1. User opens Chrome Bookmark Manager (Ctrl+Shift+O)
2. Clicks menu (⋮) → Import bookmarks
3. Selects generated HTML file
4. Chrome parses Netscape format and recreates folder structure

---

### **6. Storage & Caching (`storage.py`)**

**Purpose**: Cache management for fetched metadata to avoid redundant HTTP requests

**Main Class**: `MetadataCache`

**Key Methods**:

1. **`__init__(cache_path: Path)`**
   - **Input**: Path to cache file (default: `.bookmark_cache/metadata.json`)
   - **Processing**:
     - Creates cache directory if not exists
     - Loads existing cache from disk
     - Initializes in-memory dictionary
   - **Output**: Configured cache instance

2. **`get(url: str) -> Dict | None`**
   - **Input**: URL to lookup
   - **Processing**:
     1. Normalize URL for consistent lookup
     2. Check if URL exists in cache
     3. Validate cache age (default: 7 days max)
     4. Return cached metadata if valid
   - **Output**: 
     - Cached metadata dictionary if found and valid
     - `None` if not cached or expired

3. **`set(url: str, metadata: Dict)`**
   - **Input**: 
     - `url`: URL to cache
     - `metadata`: Fetched metadata dictionary
   - **Processing**:
     1. Normalize URL
     2. Add timestamp: `fetched_at`
     3. Store in in-memory cache
     4. Trigger async save to disk
   - **Output**: None (side effect: updates cache)

4. **`save()`**
   - **Input**: None (uses internal state)
   - **Processing**:
     1. Serialize cache dictionary to JSON
     2. Write to cache file atomically (temp file + rename)
     3. Handle write errors gracefully
   - **Output**: Cache file written to disk

5. **`load()`**
   - **Input**: None (uses cache_path)
   - **Processing**:
     1. Read JSON from cache file
     2. Parse into dictionary
     3. Validate structure
     4. Handle missing/corrupted files
   - **Output**: Dictionary loaded into memory

6. **`invalidate(url: str)`**
   - **Input**: URL to remove from cache
   - **Processing**: Delete entry from cache and save
   - **Output**: None

**Cache Structure**:
```json
{
  "https://example.com": {
    "title": "Example Domain",
    "description": "Example website for documentation",
    "keywords": ["example", "documentation"],
    "content_preview": "This domain is for use in...",
    "fetched_at": "2025-12-04T10:30:45.123456"
  },
  "https://github.com": {
    "title": "GitHub",
    "description": "Where the world builds software",
    "keywords": ["git", "code", "collaboration"],
    "content_preview": "GitHub is where over 100 million...",
    "fetched_at": "2025-12-04T10:31:12.456789"
  }
}
```

**Cache Invalidation Strategy**:
- **Time-based**: Entries older than 7 days are considered stale
- **Manual**: Can manually invalidate specific URLs
- **Error handling**: Failed fetches not cached (prevents caching errors)

**Performance Benefits**:
- Avoids re-fetching unchanged pages
- Speeds up repeated runs (e.g., testing categorization)
- Reduces network traffic and API rate limits
- Example: 309 bookmarks with 50% cache hit → 155 fewer HTTP requests

---

## **Data Flow**

### **Complete Pipeline**

```
1. Import Phase
   Chrome Bookmarks → Loader → Raw JSON
                               ↓
2. Clean Phase
   Raw JSON → Normalizer → Deduplicated JSON
                           ↓
3. Fetch Phase
   Deduplicated JSON → Fetcher → Enriched JSON
                                  ↓
4. Categorize Phase
   Enriched JSON → LLM Client → Categorized JSON
                   (Ollama/Cloud)
                                  ↓
5. Preview Phase
   Categorized JSON → Preview → User Confirmation
                                 ↓
6. Export Phase
   Categorized JSON → Exporter → Chrome Bookmarks
```

### **File Artifacts**

```
bookmarks_raw.json         # Raw flattened bookmarks
bookmarks_cleaned.json     # Deduplicated bookmarks
cleaned_tabs.log          # Removal log (CSV)
bookmarks_categorized.json # Categorized bookmarks
Bookmarks_cleaned.json    # Final Chrome format
```

---

## **Technology Stack**

### **Core Dependencies**

| Package | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `rich` | Terminal formatting |
| `httpx` | Async HTTP client |
| `beautifulsoup4` | HTML parsing |
| `lxml` | XML/HTML parser |
| `tenacity` | Retry logic |
| `aiofiles` | Async file I/O |
| `python-dotenv` | Environment variables |
| `pydantic` | Settings validation |
| `pydantic-settings` | Settings management |
| `tldextract` | URL parsing |

### **Python Version**

- **Minimum**: Python 3.11
- **Recommended**: Python 3.11+

---

## **Configuration Files**

### **1. `.env` (User Configuration)**

```env
# LLM Provider Settings
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# Ollama Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Cache Settings
CACHE_DIR=.cache
MAX_RETRIES=3
TIMEOUT=30
```

### **2. `pyproject.toml` (Project Configuration)**

- Package metadata
- Dependencies
- Entry points (`bookmark-cli` command)
- Development tools configuration

---

## **Design Patterns**

### **1. Dependency Injection**

LLM client abstraction allows swapping providers without changing caller code:

```python
llm_client = LLMClient(
    provider=settings.llm_provider,
    use_local=True  # Switch between local/cloud
)
```

### **2. Pipeline Pattern**

Sequential data transformation stages:
```
Load → Clean → Fetch → Categorize → Export
```

### **3. Async/Await**

Concurrent operations for performance:
- Metadata fetching (parallel HTTP requests)
- LLM batch processing

### **4. Retry Pattern**

Resilient error handling with exponential backoff:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_single(self, url):
    ...
```

### **5. Settings Pattern**

Centralized configuration with Pydantic:
```python
settings = Settings()  # Auto-loads from .env
```

---

## **Scalability Considerations**

### **Performance Optimizations**

1. **Batch Processing**: Group bookmarks for LLM calls
2. **Concurrency Limits**: Control parallel HTTP requests
3. **Caching**: Avoid redundant metadata fetches
4. **Streaming**: Handle large bookmark collections

### **Resource Management**

- **Memory**: Process bookmarks in batches
- **Network**: Configurable concurrency and timeouts
- **Storage**: Efficient JSON serialization

### **Local vs Cloud Trade-offs**

| Aspect | Local (Ollama) | Cloud API |
|--------|----------------|-----------|
| **Privacy** | High (data stays local) | Low (sent to provider) |
| **Cost** | Free | Pay per token |
| **Speed** | Depends on hardware | Usually faster |
| **Quality** | Model-dependent | Generally higher |
| **Setup** | Requires Ollama install | API key only |

---

## **Error Handling Strategy**

### **Graceful Degradation**

1. **Fetch Errors**: Continue with available metadata
2. **LLM Errors**: Fallback to basic categorization
3. **Parse Errors**: Return original URL

### **Logging**

- Removal logs: `cleaned_tabs.log`
- Fetch errors: Embedded in bookmark entries
- LLM errors: Console output with Rich

---

## **Security Considerations**

1. **API Keys**: Stored in `.env` (not committed to git)
2. **URL Fetching**: Configurable robots.txt respect
3. **Input Validation**: Pydantic schema validation
4. **Timeout Protection**: All HTTP requests have timeouts

---

## **Future Enhancements**

### **Planned Features**

- [ ] Database storage (SQLite)
- [ ] Web UI dashboard
- [ ] Multi-browser support (Firefox, Edge)
- [ ] Custom categorization rules
- [ ] Plugin system for extractors
- [ ] Real-time sync with browser

### **Extensibility Points**

- **LLM Providers**: Add new providers in `llm_client.py`
- **Metadata Extractors**: Extend `fetcher.py` with custom parsers
- **Export Formats**: Add new formats in `exporter.py`
- **Storage Backends**: Implement database adapters

---

## **Development Workflow**

### **Setup**

```bash
# Clone repository
git clone <repo-url>
cd bookmark-cli

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in editable mode
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

### **Testing**

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=bookmark_cli

# Type checking
mypy bookmark_cli

# Linting
ruff check bookmark_cli
```

### **Project Structure**

```
bookmark-cli/
├── bookmark_cli/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── cli.py               # CLI commands
│   ├── config.py            # Configuration
│   ├── loader.py            # Import bookmarks
│   ├── normalizer.py        # URL normalization
│   ├── fetcher.py           # Metadata fetching
│   ├── llm_client.py        # LLM abstraction
│   ├── ollama_wrapper.py    # Ollama integration
│   ├── categorizer.py       # Categorization logic
│   ├── preview.py           # Result preview
│   ├── exporter.py          # Export to Chrome
│   ├── storage.py           # Cache management
│   └── utils.py             # Utilities
├── tests/
│   ├── test_loader.py
│   ├── test_normalizer.py
│   └── ...
├── pyproject.toml           # Project config
├── README.md                # User documentation
├── ARCHITECTURE.md          # This file
└── .env.example             # Example config
```

---

## **Contribution Guidelines**

1. **Code Style**: Follow PEP 8, use Black formatter
2. **Type Hints**: Add type annotations to all functions
3. **Documentation**: Update docstrings and architecture docs
4. **Testing**: Add tests for new features
5. **Error Handling**: Use proper exception handling

---

## **References**

- [Typer Documentation](https://typer.tiangolo.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [Chrome Bookmarks Format](https://chromium.googlesource.com/chromium/src/+/master/docs/bookmarks.md)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

**Last Updated**: December 3, 2025
**Version**: 0.1.0
