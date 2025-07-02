# MarkPE + MarkAPI source code

This repository contains the source code for MarkPE, a web application for searching and downloading minecraft marketplace content, and MarkAPI, the Backend API that powers MarkPE.

## MarkPE

MarkPE is a web application that lets users search and download minecraft marketplace content. it has a simple interface for searching and downloading content, plus a progress bar to track downloads.

### features

- search for minecraft marketplace content by name, uuid, or url
- download content directly from the web app
- progress bar for tracking download progress
- user authentication and rate limiting to prevent spam

### technologies used

- react
- typescript
- css
- html

### installation

1. clone the repository
2. install dependencies with `npm install`
3. start the development server with `npm start`

### deployment

MarkPE is currently deployed on vercel and can be accessed at [https://markpe.vercel.app](https://markpe.vercel.app).

## MarkAPI

MarkAPI is a Backend API that powers markpe. it provides endpoints for searching and downloading minecraft marketplace content.

### features

- search for minecraft marketplace content by name, uuid, or url
- download content directly from the api
- rate limiting to prevent spam
- caching to improve performance

### technologies used

- python
- fastapi
- docker

### installation

1. clone the repository
2. install python dependencies with `pip install -r requirements.txt`
3. run the API with `python api.py`

### API endpoints

- `POST /api/search` - search for marketplace content
- `POST /api/download` - download content by item id

### configuration

The API requires certain configuration files:
- `keys.tsv` - decryption keys for protected content
- `personal_keys.tsv` - additional user keys (optional)

### notes

Some marketplace content requires decryption keys to process properly. Without the correct keys, downloads may fail with a **"missing decryption keys"** error.

## credits

This project was created for the Minecraft Community. Thanks to Lisa for creating this Website and Bluecoin Community for giving us permissions.

The code was written by Lisa. You are free to make changes as long as you know what you are doing.