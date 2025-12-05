# Deployment Guide - Bookmark Clustering App

## 📋 Overview

This guide covers local testing and production deployment options for the Bookmark Clustering Streamlit app.

---

## 🏠 Local Development

### Prerequisites
- Python 3.11+
- Git
- Virtual environment (recommended)

### Setup Steps

1. **Clone the repository**
```powershell
git clone https://github.com/rop2024/bookmark-clustering.git
cd bookmark-clustering
```

2. **Create virtual environment**
```powershell
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```powershell
pip install -e .
pip install streamlit
```

4. **Configure environment**
```powershell
# Copy example env file
Copy-Item .env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_api_key_here
```

5. **Run locally**
```powershell
streamlit run app.py
```

The app will open at: `http://localhost:8501`

### Testing Locally

**Test workflow:**
1. Upload a Chrome bookmarks file (HTML or JSON)
2. Clean and deduplicate
3. Categorize with AI
4. Download organized bookmarks
5. Import back into Chrome

**Performance tips:**
- Use smaller batches (20-30) for slower connections
- Disable metadata fetching for faster processing
- Test with a small subset first (~50 bookmarks)

---

## ☁️ Production Deployment

### Option 1: Streamlit Cloud (Recommended)

**Best for:** Quick deployment, free hosting, automatic updates

#### Steps:

1. **Push to GitHub** (already done)
   ```powershell
   git add .
   git commit -m "Add Streamlit app"
   git push origin main
   ```

2. **Deploy to Streamlit Cloud**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select repository: `rop2024/bookmark-clustering`
   - Main file path: `app.py`
   - Advanced settings:
     - Python version: `3.11`
     - Add secrets for `GEMINI_API_KEY`

3. **Configure Secrets**
   - Go to App Settings → Secrets
   - Add:
     ```toml
     [general]
     GEMINI_API_KEY = "your_api_key_here"
     ```

4. **Deploy**
   - Click "Deploy"
   - Wait 2-3 minutes for build
   - App URL: `https://your-app-name.streamlit.app`

#### Streamlit Cloud Features:
- ✅ Free for public repos
- ✅ Automatic HTTPS
- ✅ Auto-redeploy on git push
- ✅ Built-in secrets management
- ✅ Resource limits: 1 GB RAM, 1 CPU

---

### Option 2: Docker Container

**Best for:** Custom infrastructure, private hosting, full control

#### Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
COPY bookmark_cli/ ./bookmark_cli/
COPY app.py .

# Install Python dependencies
RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir streamlit

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run app
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

#### Build and run:

```powershell
# Build image
docker build -t bookmark-clustering .

# Run container
docker run -p 8501:8501 `
  -e GEMINI_API_KEY="your_api_key" `
  bookmark-clustering
```

Access at: `http://localhost:8501`

#### Docker Compose:

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

Run with:
```powershell
docker-compose up -d
```

---

### Option 3: Railway

**Best for:** Easy deployment, automatic scaling, modern platform

#### Steps:

1. **Install Railway CLI**
   ```powershell
   npm install -g railway
   railway login
   ```

2. **Initialize project**
   ```powershell
   railway init
   ```

3. **Add environment variables**
   ```powershell
   railway variables set GEMINI_API_KEY=your_api_key
   ```

4. **Deploy**
   ```powershell
   railway up
   ```

5. **Access app**
   ```powershell
   railway open
   ```

---

### Option 4: Heroku

**Best for:** Traditional PaaS, established platform

#### Create `Procfile`:

```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

#### Create `runtime.txt`:

```
python-3.11.6
```

#### Deploy:

```powershell
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Create app
heroku create bookmark-clustering-app

# Set environment variables
heroku config:set GEMINI_API_KEY=your_api_key

# Deploy
git push heroku main

# Open app
heroku open
```

---

### Option 5: Azure Web Apps

**Best for:** Enterprise deployment, Azure ecosystem

#### Steps:

1. **Create Azure Web App**
   - Go to Azure Portal
   - Create Web App (Python 3.11)
   - Choose pricing tier (B1 or higher)

2. **Configure deployment**
   - Set deployment source to GitHub
   - Authorize and select repository
   - Branch: `main`

3. **Add app settings**
   - `GEMINI_API_KEY`: your_api_key
   - `WEBSITES_PORT`: 8501
   - `SCM_DO_BUILD_DURING_DEPLOYMENT`: true

4. **Create startup command**
   ```bash
   python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
   ```

---

### Option 6: Google Cloud Run

**Best for:** Serverless, pay-per-use, Google Cloud ecosystem

#### Deploy:

```powershell
# Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy bookmark-clustering \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_api_key
```

---

## 🔒 Security Best Practices

### Environment Variables
- ✅ Never commit `.env` files
- ✅ Use platform secrets management
- ✅ Rotate API keys regularly

### Application Security
- ✅ Validate file uploads
- ✅ Sanitize user inputs
- ✅ Set file size limits
- ✅ Enable HTTPS only

### Example `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 50
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```

---

## 📊 Monitoring & Logging

### Streamlit Cloud
- Built-in logs viewer
- Resource usage dashboard
- App analytics

### Docker/Self-hosted
- Use Docker logs: `docker logs <container-id>`
- Set up log aggregation (ELK, Splunk)
- Monitor with Prometheus/Grafana

---

## 🚀 Performance Optimization

### Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 50
maxMessageSize = 200
enableCORS = false

[runner]
magicEnabled = true
fastReruns = true

[client]
showErrorDetails = true
```

### Caching Strategy
```python
@st.cache_data  # Cache expensive operations
def load_bookmarks_cached(file_bytes, is_html):
    # Implementation
    pass
```

### Resource Limits
- Set appropriate batch sizes (20-50)
- Limit concurrent requests (10-15)
- Use progress bars for user feedback

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Streamlit Cloud

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install streamlit
      
      - name: Run tests
        run: |
          pytest tests/
      
      # Streamlit Cloud auto-deploys on push
```

---

## 🐛 Troubleshooting

### Common Issues

**Port already in use:**
```powershell
streamlit run app.py --server.port=8502
```

**Module not found:**
```powershell
pip install -e .
```

**API key errors:**
- Check `.env` file exists
- Verify `GEMINI_API_KEY` is set
- Ensure key has correct permissions

**Memory errors:**
- Reduce batch size
- Process fewer bookmarks
- Upgrade hosting plan

---

## 📱 Access URLs

After deployment, your app will be accessible at:

- **Local**: `http://localhost:8501`
- **Streamlit Cloud**: `https://your-app-name.streamlit.app`
- **Docker**: `http://your-server-ip:8501`
- **Railway**: `https://bookmark-clustering.up.railway.app`
- **Heroku**: `https://bookmark-clustering-app.herokuapp.com`

---

## 📚 Additional Resources

- [Streamlit Deployment Guide](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app)
- [Docker Documentation](https://docs.docker.com/)
- [Google Cloud Run Guide](https://cloud.google.com/run/docs)
- [Heroku Python Guide](https://devcenter.heroku.com/articles/python-support)

---

## ✅ Deployment Checklist

Before deploying:

- [ ] Test locally with sample data
- [ ] Add `.env` to `.gitignore`
- [ ] Set up environment variables on platform
- [ ] Configure app settings (port, CORS, etc.)
- [ ] Enable HTTPS
- [ ] Set up monitoring/logging
- [ ] Document access URLs
- [ ] Test deployed app end-to-end
- [ ] Set up CI/CD (optional)

---

**Need help?** Open an issue on [GitHub](https://github.com/rop2024/bookmark-clustering/issues)
