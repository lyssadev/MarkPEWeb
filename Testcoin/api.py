from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
import json
import os
import time
import tempfile
import zipfile
import requests
from functools import lru_cache
import hashlib

import PlayFab
from coin import (
    extract_id_from_url,
    perform_search,
    login as auth_login,
    load_settings,
    auth_token
)

# Import TSV-based search functionality
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'decrypted_tsvpy'))
try:
    from tsv_plain import update_keys, check_dlc_list, read_local_file
except ImportError:
    update_keys = None
    check_dlc_list = None
    read_local_file = None

app = FastAPI(
    title="MarkPE API",
    description="MarkPE Content Search API",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=False,  # Set to False when using allow_origins=["*"]
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

@app.on_event("startup")
async def startup_event():
    """Initialize settings and authenticate on startup"""
    load_settings()
    # Authenticate once at startup to avoid rate limits
    global auth_token
    if not auth_token:
        if not auth_login():
            print("Warning: Failed to authenticate at startup")

class SearchRequest(BaseModel):
    query: str
    search_type: Optional[str] = "name"
    limit: Optional[int] = 50

class SearchResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    total: int
    query: str
    search_type: str

class DownloadRequest(BaseModel):
    item_id: str

class ErrorResponse(BaseModel):
    success: bool
    error: str
    code: int

API_KEYS = {
    hashlib.sha256("markpe_api_key_2024".encode()).hexdigest(): "internal"
}

# Rate limiting for downloads
download_rate_limit = {}
DOWNLOAD_RATE_LIMIT_SECONDS = 30  # 30 seconds between downloads per user

def search_local_data(query, search_type="name", limit=50):
    """Search using local list.txt data to bypass PlayFab rate limits"""
    results = []

    try:
        # Search in list.txt for content names
        list_file_path = os.path.join(os.path.dirname(__file__), "list.txt")
        if os.path.exists(list_file_path):
            with open(list_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Parse format: "Title ( Creator ) - Type UUID"
                        # Example: "Desert Creatures ( Everbloom Games ) - DLC 09c78020-d7df-4085-9de2-3b8e43d30c82"
                        parts = line.rsplit(' - ', 1)
                        if len(parts) != 2:
                            continue

                        title_creator = parts[0].strip()
                        type_uuid = parts[1].strip()

                        # Extract type and UUID
                        type_parts = type_uuid.split(' ', 1)
                        if len(type_parts) != 2:
                            continue

                        content_type = type_parts[0].strip()
                        uuid = type_parts[1].strip()

                        # Extract title and creator
                        if ' ( ' in title_creator and title_creator.endswith(' )'):
                            title_end = title_creator.rfind(' ( ')
                            title = title_creator[:title_end].strip()
                            creator = title_creator[title_end+3:-2].strip()
                        else:
                            title = title_creator
                            creator = "Unknown"

                        # Filter by search query
                        if query.lower() in title.lower():
                            # Convert to PlayFab-like format for compatibility
                            result = {
                                "Id": uuid,
                                "Title": {"en-US": title},
                                "DisplayProperties": {"creatorName": creator},
                                "ContentType": ["MarketplaceDurableCatalog_V1.2"],
                                "Tags": [content_type.lower()],
                                "source": "local"
                            }
                            results.append(result)

                            if len(results) >= limit:
                                break

                    except (ValueError, IndexError) as e:
                        continue

    except Exception as e:
        print(f"Error searching local data: {e}")

    return results

def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    if token_hash not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return API_KEYS[token_hash]

@lru_cache(maxsize=100)
def cached_search(query: str, search_type: str, limit: int):
    cache_key = f"{query}_{search_type}_{limit}"

    # Use the global auth_token that was set at startup
    global auth_token
    
    try:
        if "id=" in query or "minecraft.net" in query:
            extracted_id = extract_id_from_url(query)
            if extracted_id:
                result = PlayFab.main([extracted_id])
                items = list(result.values()) if result else []
                return {
                    "success": True,
                    "data": items,
                    "total": len(items),
                    "query": query,
                    "search_type": "uuid"
                }
        
        elif re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', query.strip()):
            result = PlayFab.main([query.strip()])
            items = list(result.values()) if result else []
            return {
                "success": True,
                "data": items,
                "total": len(items),
                "query": query,
                "search_type": "uuid"
            }
        
        else:
            try:
                # Try PlayFab search first
                data = perform_search(
                    query="",
                    orderBy="creationDate DESC",
                    select="contents",
                    top=min(limit, 300),
                    skip=0,
                    search_term=query,
                    search_type=search_type
                )

                items = data.get("Items", []) if isinstance(data, dict) else (data or [])

                if query and search_type == "name":
                    items = [
                        item for item in items
                        if all(term in item.get("Title", {}).get("en-US", "").lower()
                              for term in query.lower().split())
                    ]

                return {
                    "success": True,
                    "data": items[:limit],
                    "total": len(items),
                    "query": query,
                    "search_type": search_type
                }

            except Exception as playfab_error:
                # If PlayFab fails (rate limit, etc.), fall back to local search
                print(f"PlayFab search failed, using local data: {playfab_error}")

                local_results = search_local_data(query, search_type, limit)

                return {
                    "success": True,
                    "data": local_results,
                    "total": len(local_results),
                    "query": query,
                    "search_type": search_type,
                    "source": "local_fallback"
                }

    except Exception as e:
        # Final fallback to local search if everything else fails
        try:
            local_results = search_local_data(query, search_type, limit)
            return {
                "success": True,
                "data": local_results,
                "total": len(local_results),
                "query": query,
                "search_type": search_type,
                "source": "local_emergency_fallback"
            }
        except:
            raise HTTPException(status_code=500, detail=f"All search methods failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "MarkPE API v1.0", "status": "online"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0", "service": "MarkPE API"}

@app.get("/api/test")
async def test_endpoint():
    return {
        "success": True,
        "data": [
            {
                "Id": "12345678-1234-1234-1234-123456789abc",
                "Title": {"en-US": "Test Minecraft Skin Pack"},
                "DisplayProperties": {"creatorName": "Test Creator"},
                "Tags": ["skinpack"],
                "ContentType": ["MarketplaceDurableCatalog_V1.2"]
            },
            {
                "Id": "87654321-4321-4321-4321-cba987654321",
                "Title": {"en-US": "Sample Resource Pack"},
                "DisplayProperties": {"creatorName": "Sample Creator"},
                "Tags": ["resourcepack"],
                "ContentType": ["MarketplaceDurableCatalog_V1.2"]
            }
        ],
        "total": 2,
        "query": "test",
        "search_type": "name"
    }

@app.post("/api/search", response_model=SearchResponse)
async def search_content(
    request: SearchRequest,
    api_user: str = Depends(verify_api_key)
):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    if request.limit and (request.limit < 1 or request.limit > 300):
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 300")
    
    valid_types = ["name", "texture", "mashup", "addon", "persona", "capes", "hidden", "skin", "newest"]
    if request.search_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid search type. Must be one of: {valid_types}")
    
    try:
        result = cached_search(request.query, request.search_type, request.limit or 50)
        return SearchResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/search")
async def search_content_get(
    q: str = Query(..., description="Search query"),
    type: str = Query("name", description="Search type"),
    limit: int = Query(50, description="Result limit"),
    api_user: str = Depends(verify_api_key)
):
    request = SearchRequest(query=q, search_type=type, limit=limit)
    return await search_content(request, api_user)

@app.post("/api/search-local", response_model=SearchResponse)
async def search_local_only(
    request: SearchRequest,
    api_user: str = Depends(verify_api_key)
):
    """Search using only local data, completely bypassing PlayFab"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        results = search_local_data(request.query, request.search_type, request.limit or 50)

        return SearchResponse(
            success=True,
            data=results,
            total=len(results),
            query=request.query,
            search_type=request.search_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local search failed: {str(e)}")

@app.get("/api/search-local")
async def search_local_only_get(
    q: str = Query(..., description="Search query"),
    type: str = Query("name", description="Search type"),
    limit: int = Query(50, description="Result limit"),
    api_user: str = Depends(verify_api_key)
):
    """Search using only local data, completely bypassing PlayFab"""
    request = SearchRequest(query=q, search_type=type, limit=limit)
    return await search_local_only(request, api_user)

def check_download_rate_limit(user_id: str) -> bool:
    """Check if user can download (rate limiting)"""
    current_time = time.time()
    if user_id in download_rate_limit:
        last_download = download_rate_limit[user_id]
        if current_time - last_download < DOWNLOAD_RATE_LIMIT_SECONDS:
            return False
    download_rate_limit[user_id] = current_time
    return True

async def download_content_from_playfab(item_id: str) -> tuple[bytes, str]:
    """Download content from PlayFab and return bytes and filename"""
    try:
        # Use the exact same method that works in coin.py
        result = PlayFab.main([item_id])

        if not result or item_id not in result:
            raise HTTPException(status_code=404, detail="Content not found")

        item = result[item_id]
        title = item.get("Title", {}).get("en-US", "Unknown")
        contents = item.get("Contents", [])

        if not contents:
            raise HTTPException(status_code=404, detail="No downloadable content found")

        # Get the first available download URL
        download_url = None
        for content in contents:
            if "Url" in content:
                download_url = content["Url"]
                break

        if not download_url:
            raise HTTPException(status_code=404, detail="No download URL found")

        # Download the content
        headers = {"User-Agent": "libhttpclient/1.0.0.0"}
        response = requests.get(download_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        # Read content into memory
        content_data = b""
        for chunk in response.iter_content(chunk_size=8192):
            content_data += chunk

        # Generate filename
        filename = f"{title.replace(' ', '_').replace('/', '_')}.zip"
        # Remove any invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        return content_data, filename

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.post("/api/download")
async def download_content(
    request: DownloadRequest,
    api_user: str = Depends(verify_api_key)
):
    """Download content package by item ID"""

    # Check rate limiting
    if not check_download_rate_limit(api_user):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {DOWNLOAD_RATE_LIMIT_SECONDS} seconds between downloads."
        )

    try:
        content_data, filename = await download_content_from_playfab(request.item_id)

        # Return as streaming response
        def generate():
            yield content_data

        return StreamingResponse(
            generate(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content_data))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

if __name__ == "__main__":
    # Initialize settings on startup
    load_settings()

    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)