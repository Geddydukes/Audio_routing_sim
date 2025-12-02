# Hosting AERS on GitHub Pages + Backend Service

## Overview

GitHub Pages can only serve static files (HTML/CSS/JS). Since AERS requires a Python FastAPI backend with WebSockets, we need to split hosting:

- **Frontend**: GitHub Pages (free, static hosting)
- **Backend**: Render.com, Railway, or Fly.io (free tier available)

## Option 1: Render.com (Recommended - Free Tier)

### Backend Setup

1. **Create `render.yaml`** in project root:
```yaml
services:
  - type: web
    name: aers-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: PYTHONPATH=src uvicorn aers.ui.server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
```

2. **Deploy to Render**:
   - Push to GitHub
   - Connect repo to Render.com
   - Render auto-detects `render.yaml`
   - Get backend URL: `https://aers-api.onrender.com`

3. **Update Frontend**:
   - Change `API_HOST` in `ui/dashboard/app.js` and `graph-editor.js` to your Render URL
   - Use environment variable or build-time config

### Frontend Setup

1. **Create `.github/workflows/deploy-pages.yml`**:
```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Build frontend
        run: |
          cd ui/dashboard
          # Replace API_HOST with your Render URL
          sed -i 's|localhost:8000|aers-api.onrender.com|g' app.js graph-editor.js
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./ui/dashboard
```

2. **Enable GitHub Pages**:
   - Settings → Pages → Source: `gh-pages` branch

## Option 2: Railway.app (Free Tier)

### Backend Setup

1. **Create `Procfile`**:
```
web: PYTHONPATH=src uvicorn aers.ui.server:app --host 0.0.0.0 --port $PORT
```

2. **Deploy**:
   - Connect GitHub repo to Railway
   - Railway auto-detects Python project
   - Get URL: `https://aers-api.railway.app`

3. **Update Frontend** (same as Render)

## Option 3: Fly.io (Free Tier)

### Backend Setup

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`

2. **Create `fly.toml`**:
```toml
app = "aers-api"
primary_region = "iad"

[build]

[env]
  PORT = "8080"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

3. **Deploy**: `flyctl launch` then `flyctl deploy`

## Frontend Configuration

### Environment-Based API Host

Create `ui/dashboard/config.js`:
```javascript
// Auto-detect API host
const API_HOST = (() => {
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'localhost:8000';
  }
  // Production: use your backend URL
  return 'aers-api.onrender.com'; // or your Railway/Fly.io URL
})();
```

Then update `app.js` and `graph-editor.js`:
```javascript
// Remove hardcoded localhost:8000
// Use: const API_HOST = window.API_HOST || 'localhost:8000';
```

## Quick Setup Script

Create `scripts/setup_github_pages.sh`:
```bash
#!/bin/bash
# Update frontend to use production API URL

BACKEND_URL="${1:-aers-api.onrender.com}"

cd ui/dashboard

# Update app.js
sed -i.bak "s|localhost:8000|${BACKEND_URL}|g" app.js

# Update graph-editor.js  
sed -i.bak "s|localhost:8000|${BACKEND_URL}|g" graph-editor.js

echo "✅ Updated frontend to use backend: ${BACKEND_URL}"
echo "📝 Commit and push, then enable GitHub Pages"
```

## Limitations

- **WebSocket over HTTPS**: Render/Railway use HTTPS, so WebSocket URLs must be `wss://` not `ws://`
- **Free tier timeouts**: Render free tier sleeps after 15min inactivity
- **CORS**: Ensure backend allows your GitHub Pages domain

## Testing Locally

Before deploying, test with production-like setup:
```bash
# Terminal 1: Backend
PYTHONPATH=src uvicorn aers.ui.server:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend (served from different port)
cd ui/dashboard
python -m http.server 4173

# Update app.js to use localhost:8000 for testing
```

## Recommended Approach

1. **Backend**: Render.com (easiest, free tier)
2. **Frontend**: GitHub Pages (automatic deployment)
3. **Update**: Use environment detection in frontend code

This gives you:
- ✅ Free hosting for both
- ✅ Automatic deployments
- ✅ Professional URLs
- ✅ Full functionality



