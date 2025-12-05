# 📚 Bookmark Clustering & Organization

A powerful tool for organizing Chrome bookmarks with AI-powered categorization using Google Gemini. Available as both a **CLI tool** and a **web application**.

## 🌟 Features

- **Import & Flatten**: Load Chrome bookmarks from JSON or HTML format
- **Clean & Deduplicate**: Normalize URLs and remove duplicates  
- **Smart Categorization**: Use Google Gemini AI to categorize bookmarks based on content
- **Metadata Fetching**: Automatically fetch titles, descriptions, and metadata
- **Folder Building**: Create organized folders with intelligent splitting
- **Preview**: Review organization before applying changes
- **Export**: Export to Chrome-compatible HTML format

## 🚀 Quick Start

### Web Application (Recommended)

The easiest way to use the tool is through the **Streamlit web interface**:

```powershell
# Install dependencies
pip install -e .
pip install streamlit

# Run the web app
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

### CLI Tool

For command-line enthusiasts:

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd bookmark-cli

# Install dependencies
pip install -e .
```

## Setup

1. **Get a Gemini API Key**
   - Visit https://makersuite.google.com/app/apikey
   - Create a free API key (no credit card required)

2. **Configure Environment**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env and add your API key:
   # GEMINI_API_KEY=your_api_key_here
   ```

## Usage

### 1. Import Bookmarks

Export your Chrome bookmarks:
- Chrome → Bookmarks → Bookmark Manager (Ctrl+Shift+O)
- Click "⋮" → Export bookmarks → Save as `bookmarks.html`

Import into the tool:
```bash
# From HTML (recommended)
bookmark-cli import bookmarks.html

# From JSON (also supported)
bookmark-cli import bookmarks.json
```

### 2. Clean & Normalize

Remove duplicates and normalize URLs:
```bash
bookmark-cli clean
```

### 3. Categorize with AI

Use Google Gemini to intelligently categorize your bookmarks:
```bash
# Basic categorization
bookmark-cli categorize

# With custom batch size (default: 50)
bookmark-cli categorize --batch-size 30

# Without metadata fetching (faster but less accurate)
bookmark-cli categorize --no-fetch-metadata
```

The tool will:
- Analyze bookmark content and URLs
- Assign relevant categories/folders
- Add descriptive tags
- Handle graceful shutdown with Ctrl+C (progress is saved)

### 4. View Statistics

```bash
bookmark-cli stats
```

Shows:
- Total bookmarks
- Categories distribution
- Tags frequency
- Uncategorized items

### 5. Export Organized Bookmarks

```bash
bookmark-cli export organized_bookmarks.html
```

Import back into Chrome:
- Chrome → Bookmarks → Bookmark Manager
- Click "⋮" → Import bookmarks → Select `organized_bookmarks.html`

## Configuration

Edit `.env` to customize:

```bash
# Google Gemini API
GEMINI_API_KEY=your_api_key_here
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash

# Processing Settings
BATCH_SIZE=50                  # Bookmarks per API call
MAX_FOLDER_SIZE=6             # Max bookmarks before splitting folder
FETCH_CONCURRENCY=10          # Concurrent metadata fetches
RESPECT_ROBOTS=true           # Honor robots.txt
```

## Advanced Usage

### Workflow Automation

```bash
# Complete workflow in one go
bookmark-cli import bookmarks.html && \
bookmark-cli clean && \
bookmark-cli categorize --batch-size 50 && \
bookmark-cli export final_bookmarks.html
```

### Progress Recovery

If categorization is interrupted:
```bash
# Progress is automatically saved to .categorization_progress.json
# Just run categorize again to resume:
bookmark-cli categorize
```

### Custom Model Settings

```bash
# Use different Gemini model
export LLM_MODEL=gemini-1.5-pro

# Adjust batch size for rate limits
bookmark-cli categorize --batch-size 20
```

## 📦 Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment guides:
- Local testing
- Streamlit Cloud (free hosting)
- Docker containers
- Railway, Heroku, Azure, Google Cloud Run

## 🏗️ Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## 🔧 Troubleshooting

### API Key Issues
```
Error: Gemini API key not found!
```
**Solution**: Ensure `.env` contains `GEMINI_API_KEY=your_key`

### Port Already in Use
```powershell
# Use a different port
streamlit run app.py --server.port=8502
```

### Memory Issues
- Reduce batch size (20-30)
- Process fewer bookmarks at once
- Disable metadata fetching for faster processing

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📞 Support

- Documentation: [README.md](README.md)
- Deployment Guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Streamlit Features: [STREAMLIT_IMPLEMENTATION.md](STREAMLIT_IMPLEMENTATION.md)
- Issues: [GitHub Issues](https://github.com/rop2024/bookmark-clustering/issues)

### Rate Limiting
```
Error: API rate limit exceeded
```
**Solution**: Reduce batch size: `bookmark-cli categorize --batch-size 20`

### Import Errors
```
Error: Failed to parse bookmarks
```
**Solution**: Ensure HTML/JSON is valid Chrome export format

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or PR.
