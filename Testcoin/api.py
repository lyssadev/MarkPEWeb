from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import re
import json
import os
import time
import tempfile
import zipfile
import requests
from functools import lru_cache
import hashlib
import shutil
import uuid as uuid_module
import asyncio
import concurrent.futures
from threading import Lock

# ███╗   ███╗ █████╗ ██████╗ ██╗  ██╗ █████╗ ██████╗ ██╗
# ████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔══██╗██║
# ██╔████╔██║███████║██████╔╝█████╔╝ ███████║██████╔╝██║
# ██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══██║██╔═══╝ ██║
# ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██║  ██║██║     ██║
# ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
#
# This code was written by Lisa, you are free to make any changes as long as you know what you are doing :3

import PlayFab
from coin import (
    extract_id_from_url,
    perform_search,
    login as auth_login,
    load_settings,
    auth_token
)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'decrypted_tsvpy'))
try:
    from tsv_plain import update_keys, check_dlc_list, read_local_file
except ImportError:
    update_keys = None
    check_dlc_list = None
    read_local_file = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_settings()
    global auth_token
    if not auth_token:
        if not auth_login():
            print("Warning: Failed to authenticate at startup")
    yield

app = FastAPI(
    title="MarkPE API",
    description="MarkPE Content Search API",
    version="1.2",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

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
    process_content: Optional[bool] = False

class ErrorResponse(BaseModel):
    success: bool
    error: str
    code: int

API_KEYS = {
    hashlib.sha256("markpe_api_key_2024".encode()).hexdigest(): "internal"
}

download_rate_limit = {}
active_downloads = {}
download_lock = Lock()
DOWNLOAD_RATE_LIMIT_SECONDS = 5
MAX_CONCURRENT_DOWNLOADS_PER_USER = 3
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

def search_local_data(query, search_type="name", limit=50):
    results = []

    try:
        list_file_path = os.path.join(os.path.dirname(__file__), "list.txt")
        if os.path.exists(list_file_path):
            with open(list_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.rsplit(' - ', 1)
                        if len(parts) != 2:
                            continue

                        title_creator = parts[0].strip()
                        type_uuid = parts[1].strip()

                        type_parts = type_uuid.split(' ', 1)
                        if len(type_parts) != 2:
                            continue

                        content_type = type_parts[0].strip()
                        uuid = type_parts[1].strip()

                        if ' ( ' in title_creator and title_creator.endswith(' )'):
                            title_end = title_creator.rfind(' ( ')
                            title = title_creator[:title_end].strip()
                            creator = title_creator[title_end+3:-2].strip()
                        else:
                            title = title_creator
                            creator = "Unknown"

                        if query.lower() in title.lower():
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

def enrich_local_results_with_images(results):
    """Enrich local search results with image data from PlayFab"""
    enriched_results = []

    if not results:
        return enriched_results

    try:
        item_ids = [result["Id"] for result in results]

        playfab_data = PlayFab.main(item_ids)

        if playfab_data:
            for result in results:
                item_id = result["Id"]
                if item_id in playfab_data:
                    playfab_item = playfab_data[item_id]
                    result["Images"] = playfab_item.get("Images", [])

                enriched_results.append(result)
        else:
            enriched_results = results

    except Exception as e:
        print(f"Error enriching local results with images: {e}")
        enriched_results = results

    return enriched_results

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
                data = perform_search(
                    query="",
                    orderBy="creationDate DESC",
                    select="contents,images",
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
                print(f"PlayFab search failed, using local data: {playfab_error}")

                local_results = search_local_data(query, search_type, limit)
                enriched_results = enrich_local_results_with_images(local_results)

                return {
                    "success": True,
                    "data": enriched_results,
                    "total": len(enriched_results),
                    "query": query,
                    "search_type": search_type,
                    "source": "local_fallback"
                }

    except Exception as e:
        try:
            local_results = search_local_data(query, search_type, limit)
            enriched_results = enrich_local_results_with_images(local_results)
            return {
                "success": True,
                "data": enriched_results,
                "total": len(enriched_results),
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

@app.get("/api/test-item-structure")
async def test_item_structure(item_id: str = Query(..., description="Item ID to test"), api_user: str = Depends(verify_api_key)):
    """Test endpoint to see what fields are available in PlayFab items"""
    try:
        result = PlayFab.main([item_id])

        if not result or item_id not in result:
            raise HTTPException(status_code=404, detail="Content not found")

        item = result[item_id]

        return {
            "success": True,
            "item_id": item_id,
            "available_fields": list(item.keys()),
            "full_item_data": item
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get item structure: {str(e)}")

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
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        results = search_local_data(request.query, request.search_type, request.limit or 50)
        enriched_results = enrich_local_results_with_images(results)

        return SearchResponse(
            success=True,
            data=enriched_results,
            total=len(enriched_results),
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
    request = SearchRequest(query=q, search_type=type, limit=limit)
    return await search_local_only(request, api_user)

def check_download_rate_limit(user_id: str) -> bool:
    with download_lock:
        current_time = time.time()

        if user_id not in active_downloads:
            active_downloads[user_id] = []

        active_downloads[user_id] = [
            timestamp for timestamp in active_downloads[user_id]
            if current_time - timestamp < DOWNLOAD_RATE_LIMIT_SECONDS
        ]

        if len(active_downloads[user_id]) >= MAX_CONCURRENT_DOWNLOADS_PER_USER:
            return False

        active_downloads[user_id].append(current_time)
        return True

def release_download_slot(user_id: str, start_time: float):
    with download_lock:
        if user_id in active_downloads:
            try:
                active_downloads[user_id].remove(start_time)
            except ValueError:
                pass

async def get_download_info_from_playfab(item_id: str) -> tuple[str, str, dict]:
    try:
        result = PlayFab.main([item_id])

        if not result or item_id not in result:
            raise HTTPException(status_code=404, detail="Content not found")

        item = result[item_id]
        title = item.get("Title", {}).get("en-US", "Unknown")
        contents = item.get("Contents", [])

        if not contents:
            raise HTTPException(status_code=404, detail="No downloadable content found")

        content_info = {
            "title": title,
            "content_types": [],
            "playfab_content_types": [],
            "playfab_contents": contents,
            "total_files": len(contents),
            "has_multiple_types": False
        }

        for content in contents:
            content_type = content.get("Type", "")
            if content_type:
                content_info["playfab_content_types"].append(content_type)

        tags = item.get("Tags", [])
        for tag in tags:
            tag_lower = tag.lower()
            if "skin" in tag_lower:
                content_info["content_types"].append("Skin Pack")
            elif "resource" in tag_lower or "texture" in tag_lower:
                content_info["content_types"].append("Resource Pack")
            elif "addon" in tag_lower or "behavior" in tag_lower:
                content_info["content_types"].append("Add-On")
            elif "world" in tag_lower or "map" in tag_lower:
                content_info["content_types"].append("World")
            elif "mashup" in tag_lower:
                content_info["content_types"].append("Mashup Pack")

        for content_type in content_info["playfab_content_types"]:
            if content_type in {"skinbinary", "personabinary"}:
                if "Skin Pack" not in content_info["content_types"]:
                    content_info["content_types"].append("Skin Pack")

        if not content_info["content_types"]:
            if len(contents) > 1:
                content_info["content_types"].append("Mixed Content")
            else:
                content_info["content_types"].append("Content Pack")

        content_info["has_multiple_types"] = len(content_info["content_types"]) > 1 or len(contents) > 1

        download_url = None
        for content in contents:
            if "Url" in content:
                download_url = content["Url"]
                break

        if not download_url:
            raise HTTPException(status_code=404, detail="No download URL found")

        content_type_str = " + ".join(content_info["content_types"]) if content_info["content_types"] else "Content"
        if content_info["has_multiple_types"]:
            filename = f"{title.replace(' ', '_').replace('/', '_')}_({content_type_str}).zip"
        else:
            filename = f"{title.replace(' ', '_').replace('/', '_')}.zip"

        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        return download_url, filename, content_info

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get download info: {str(e)}")

def load_keys_from_files():
    files_to_check = ["keys.tsv", "personal_keys.tsv"]
    loaded_lines = []

    for file_name in files_to_check:
        try:
            with open(file_name, "r") as keys_file:
                loaded_lines.extend(keys_file.readlines())
        except FileNotFoundError:
            if file_name == "keys.tsv":
                print("'keys.tsv' file not found.")
            continue

    return loaded_lines

def check_custom_id(custom_ids, loaded_lines):
    if isinstance(custom_ids, str):
        custom_ids = {custom_ids}
    elif isinstance(custom_ids, list):
        custom_ids = set(custom_ids)

    for line in loaded_lines:
        for id in custom_ids:
            if id in line:
                return True

    return False

def process_content_like_coin_sync(item_id: str, download_url: str, title: str, content_info: dict) -> tuple[str, str]:
    import tempfile
    import shutil
    import os
    import zipfile
    import coin
    import dlc

    temp_dir = tempfile.mkdtemp(prefix="markpe_temp_")
    download_output_folder = os.path.join(temp_dir, "download")
    final_output_folder = os.path.join(temp_dir, "output")
    os.makedirs(download_output_folder, exist_ok=True)
    os.makedirs(final_output_folder, exist_ok=True)

    try:
        print(f"Processing content: {title}")
        print(f"Download URL: {download_url}")

        loaded_keys = load_keys_from_files()
        has_key_available = check_custom_id(item_id, loaded_keys)
        print(f"Key availability check for {item_id}: {has_key_available}")

        skin_urls = []
        other_urls = []

        playfab_contents = content_info.get("playfab_contents", [])
        for content in playfab_contents:
            content_type = content.get("Type", "")
            if content_type in {"skinbinary", "personabinary"}:
                skin_urls.append(content["Url"])
            elif has_key_available:
                other_urls.append(content["Url"])
            else:
                other_urls.append(content["Url"])
                print(f"No key found for {item_id}, attempting to process {content_type} anyway")

        print(f"Found {len(skin_urls)} skin URLs and {len(other_urls)} other URLs")

        processed_files = []

        all_urls = other_urls + skin_urls
        for url_index, url in enumerate(all_urls):
            print(f"Processing URL {url_index + 1}/{len(all_urls)}: {url}")

            extracted_pack_folders = coin.download_and_process_zip(url, download_output_folder)
            if extracted_pack_folders is None:
                print(f"Failed to download and extract from URL: {url}")
                continue

            print(f"Extracted {len(extracted_pack_folders)} pack folders from URL")

            is_skin = url in skin_urls

            if is_skin:
                for folder_name, pack_folder in extracted_pack_folders:
                    try:
                        first_uuid = coin.data_uuid(pack_folder)
                        print(f"Processing skin pack: {folder_name}")

                        dlc.skin_main(pack_folder, final_output_folder)

                        for output_file in os.listdir(final_output_folder):
                            if output_file.endswith(('.mcpack', '.zip')) and output_file not in processed_files:
                                processed_files.append(output_file)
                                print(f"Created skin pack: {output_file}")

                    except Exception as e:
                        print(f"Skin processing failed for {folder_name}: {e}")
                        coin.log_error(first_uuid if 'first_uuid' in locals() else None, e)
            else:
                addon_folders = []
                dlc_folders = []

                for folder_name, pack_folder in extracted_pack_folders:
                    is_addon_flag = coin.check_for_addon(pack_folder)
                    if is_addon_flag:
                        addon_folders.append(pack_folder)
                        print(f"Identified addon folder: {folder_name}")
                    else:
                        dlc_folders.append(pack_folder)
                        print(f"Identified DLC/resource folder: {folder_name}")

                if addon_folders:
                    try:
                        print(f"Processing {len(addon_folders)} addon folders")
                        dlc.main(addon_folders, ["keys.tsv", "personal_keys.tsv"], final_output_folder, is_addon=True)

                        for output_file in os.listdir(final_output_folder):
                            if output_file.endswith(('.mcaddon', '.mcpack')) and output_file not in processed_files:
                                processed_files.append(output_file)
                                print(f"Created addon: {output_file}")
                    except Exception as e:
                        print(f"Addon processing failed: {e}")

                if dlc_folders:
                    try:
                        print(f"Processing {len(dlc_folders)} DLC folders")
                        dlc.main(dlc_folders, ["keys.tsv", "personal_keys.tsv"], final_output_folder, is_addon=False)

                        for output_file in os.listdir(final_output_folder):
                            if output_file.endswith(('.mcpack', '.mctemplate')) and output_file not in processed_files:
                                processed_files.append(output_file)
                                print(f"Created DLC/resource: {output_file}")
                    except Exception as e:
                        print(f"DLC processing failed: {e}")

        print(f"Found {len(processed_files)} processed files: {processed_files}")

        if not processed_files:
            error_msg = f"No content files were successfully processed for '{title}' (ID: {item_id}). "
            if not has_key_available and not skin_urls:
                error_msg = "This content requires decryption keys that are not available. Try adding the required keys to keys.tsv or personal_keys.tsv files."
                # Raise a specific HTTPException for missing keys
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "missing_decryption_keys",
                        "message": error_msg,
                        "title": title,
                        "item_id": item_id
                    }
                )
            elif not all_urls:
                error_msg += "No downloadable content URLs were found in the PlayFab response."
            else:
                error_msg += f"Processing failed for all {len(all_urls)} content URLs."
            raise Exception(error_msg)

        if len(processed_files) > 1:
            zip_filename = f"{title.replace(' ', '_').replace('/', '_')}_content.zip"
            zip_path = os.path.join(final_output_folder, zip_filename)

            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in processed_files:
                    file_path = os.path.join(final_output_folder, file)
                    if os.path.exists(file_path):
                        zipf.write(file_path, file)

            file_size = os.path.getsize(zip_path)
            print(f"Created combined ZIP: {zip_filename} ({file_size} bytes)")
            return zip_filename, zip_path
        else:
            filename = processed_files[0]
            file_path = os.path.join(final_output_folder, filename)
            file_size = os.path.getsize(file_path)
            print(f"Returning single processed file: {filename} ({file_size} bytes)")
            return filename, file_path

    except Exception as e:
        print(f"Content processing failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Content processing failed: {str(e)}")
    finally:
        if os.path.exists(download_output_folder):
            shutil.rmtree(download_output_folder, ignore_errors=True)

async def process_content_like_coin(item_id: str, download_url: str, title: str, content_info: dict) -> tuple[str, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        thread_pool,
        process_content_like_coin_sync,
        item_id, download_url, title, content_info
    )

def stream_download_from_url(download_url: str):
    """Stream download from URL with proper chunking"""
    try:
        headers = {"User-Agent": "libhttpclient/1.0.0.0"}
        response = requests.get(download_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

def stream_file_from_path(file_path: str):
    """Stream file directly from disk to avoid memory issues"""
    try:
        with open(file_path, 'rb') as f:
            chunk_size = 8192
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File streaming failed: {str(e)}")

@app.post("/api/download")
async def download_content(
    request: DownloadRequest,
    api_user: str = Depends(verify_api_key)
):
    download_start_time = time.time()

    if not check_download_rate_limit(api_user):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {MAX_CONCURRENT_DOWNLOADS_PER_USER} concurrent downloads allowed per user."
        )

    try:
        download_url, filename, content_info = await get_download_info_from_playfab(request.item_id)

        if request.process_content:
            processed_filename, file_path = await process_content_like_coin(request.item_id, download_url, content_info["title"], content_info)

            if processed_filename.endswith('.zip'):
                media_type = "application/zip"
            elif processed_filename.endswith('.mcpack'):
                media_type = "application/octet-stream"
            elif processed_filename.endswith('.mctemplate'):
                media_type = "application/octet-stream"
            elif processed_filename.endswith('.mcaddon'):
                media_type = "application/octet-stream"
            else:
                media_type = "application/zip"

            file_size = os.path.getsize(file_path)

            def file_streamer():
                try:
                    yield from stream_file_from_path(file_path)
                finally:
                    output_dir = os.path.dirname(file_path)
                    try:
                        shutil.rmtree(output_dir, ignore_errors=True)
                    except:
                        pass
                    release_download_slot(api_user, download_start_time)

            response_headers = {
                "Content-Disposition": f'attachment; filename="{processed_filename}"',
                "X-Content-Types": ", ".join(content_info["content_types"]),
                "X-Content-Title": content_info["title"],
                "X-Total-Files": str(content_info["total_files"]),
                "X-Has-Multiple-Types": str(content_info["has_multiple_types"]).lower(),
                "X-Processed": "true",
                "Content-Length": str(file_size)
            }

            return StreamingResponse(
                file_streamer(),
                media_type=media_type,
                headers=response_headers
            )
        else:
            headers = {"User-Agent": "libhttpclient/1.0.0.0"}
            head_response = requests.head(download_url, headers=headers, timeout=30)
            content_length = head_response.headers.get('content-length')

            response_headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Types": ", ".join(content_info["content_types"]),
                "X-Content-Title": content_info["title"],
                "X-Total-Files": str(content_info["total_files"]),
                "X-Has-Multiple-Types": str(content_info["has_multiple_types"]).lower(),
                "X-Processed": "false"
            }

            if content_length:
                response_headers["Content-Length"] = content_length

            def raw_file_streamer():
                try:
                    yield from stream_download_from_url(download_url)
                finally:
                    release_download_slot(api_user, download_start_time)

            return StreamingResponse(
                raw_file_streamer(),
                media_type="application/zip",
                headers=response_headers
            )

    except HTTPException:
        release_download_slot(api_user, download_start_time)
        raise
    except Exception as e:
        release_download_slot(api_user, download_start_time)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

if __name__ == "__main__":
    load_settings()

    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, loop="asyncio")