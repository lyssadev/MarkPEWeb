# MarkPE Vercel Deployment Guide

## Security Setup

### 1. Environment Variables in Vercel

After deploying to Vercel, you MUST set these environment variables in your Vercel dashboard:

1. Go to your Vercel project dashboard
2. Navigate to Settings → Environment Variables
3. Add the following variables:

```
PLAYFAB_CUSTOM_ID=MCPF55A9D163E082C436C73F04D9437DC440
PLAYFAB_PLAYER_SECRET=Cx08WTdhghuF6m24Kn8JWyxvfuWaIFquxR4AT1zNUS0=
MARKPE_API_KEY=markpe_api_key_2024
```

### 2. Security Benefits

- ✅ **API credentials protected**: PlayFab secrets are not exposed in source code
- ✅ **API key secured**: Authentication token stored securely
- ✅ **Source code safe**: No sensitive data in repository
- ✅ **Environment isolation**: Different keys for development/production

### 3. Local Development

For local development, the `.env.local` file contains the environment variables.
This file is ignored by git for security.

## Deployment Steps

1. **Deploy to Vercel**:
   ```bash
   cd testcoin-web
   vercel
   ```

2. **Set Environment Variables** in Vercel dashboard (required!)

3. **Test the deployment** by accessing your Vercel URL

## API Security Features

- Bearer token authentication required for all API calls
- Rate limiting on download endpoints (30 seconds between downloads)
- Environment variable protection for sensitive credentials
- CORS configuration for secure cross-origin requests

## Important Notes

- Never commit `.env.local` or `api/settings.json` with real credentials
- Always set environment variables in Vercel dashboard before first use
- The API will fallback to settings.json if environment variables are not set
