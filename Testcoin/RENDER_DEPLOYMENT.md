# Render Deployment Guide

## Quick Fix for Current Issue

The deployment failed due to a `pydantic-core` compilation issue. Here are the solutions:

### Option 1: Use Docker (Recommended)

1. **Update your Render service settings:**
   - Environment: `Docker`
   - Build Command: (leave empty)
   - Start Command: (leave empty)
   - Root Directory: `Testcoin`

2. **The Dockerfile is already created and will:**
   - Use Python 3.11 for better compatibility
   - Install system dependencies needed for compilation
   - Handle the build process automatically

### Option 2: Fix Python Version

1. **Update your Render service settings:**
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `./start.sh`
   - Root Directory: `Testcoin`

2. **The `runtime.txt` file specifies Python 3.11.9** which should avoid the compilation issues.

### Option 3: Alternative Requirements

If both above fail, try this minimal approach:

1. Replace `requirements.txt` with:
```
fastapi
uvicorn[standard]
requests
pycryptodome
python-multipart
```

## Current Status

- ✅ Updated `requirements.txt` with compatible versions
- ✅ Added `runtime.txt` for Python 3.11.9
- ✅ Created `Dockerfile` for Docker deployment
- ✅ Fixed port configuration in `api.py`

## Next Steps

1. **Push the changes to GitHub**
2. **Try Option 1 (Docker) first** - it's most reliable
3. **If Docker doesn't work, try Option 2** with the runtime.txt
4. **Monitor the build logs** for any remaining issues

## Testing After Deployment

Once deployed successfully, test with:

```bash
# Health check
curl https://your-app.onrender.com/api/health

# Search test
curl -X POST "https://your-app.onrender.com/api/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer markpe_api_key_2024" \
  -d '{"query": "test", "search_type": "name", "limit": 5}'
```

## Frontend Configuration

Update your frontend `.env`:
```
REACT_APP_API_URL=https://your-app.onrender.com
```
