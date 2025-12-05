# bookmark-cli/README.md
# Bookmark Organizer CLI

A powerful CLI tool for organizing Chrome bookmarks with LLM assistance.

## Features

- **Import & Flatten**: Load Chrome bookmarks JSON and flatten nested structure
- **Clean & Deduplicate**: Normalize URLs and remove duplicates
- **Smart Categorization**: Use LLM to categorize bookmarks based on content
- **Metadata Fetching**: Automatically fetch titles, descriptions, and metadata
- **Folder Building**: Create organized folders with intelligent splitting
- **Preview**: Review organization before applying changes
- **Export**: Export back to Chrome-compatible format

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd bookmark-cli

# Install dependencies
pip install -e .
```

## **Local LLM Support with Ollama**

The tool supports local LLMs via [Ollama](https://ollama.ai/) for privacy and cost-free categorization.

### **Setup Ollama**

1. **Install Ollama:**
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows (via Winget)
   winget install ollama.ollama