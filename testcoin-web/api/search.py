import json
import re
import hashlib
from http.server import BaseHTTPRequestHandler
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Testcoin'))

try:
    import PlayFab
    from coin import extract_id_from_url, perform_search, login as auth_login, auth_token
except ImportError:
    PlayFab = None

API_KEYS = {
    hashlib.sha256("markpe_api_key_2024".encode()).hexdigest(): "internal"
}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path != '/api/search':
                self.send_error(404, "Not Found")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                self.send_error(401, "API key required")
                return
            
            token = auth_header[7:]
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if token_hash not in API_KEYS:
                self.send_error(401, "Invalid API key")
                return
            
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            query = request_data.get('query', '').strip()
            search_type = request_data.get('search_type', 'name')
            limit = min(request_data.get('limit', 50), 300)
            
            if not query:
                self.send_error(400, "Query cannot be empty")
                return
            
            valid_types = ["name", "texture", "mashup", "addon", "persona", "capes", "hidden", "skin", "newest"]
            if search_type not in valid_types:
                self.send_error(400, f"Invalid search type. Must be one of: {valid_types}")
                return
            
            if not PlayFab:
                self.send_error(500, "PlayFab module not available")
                return
            
            global auth_token
            if not auth_token:
                if not auth_login():
                    self.send_error(500, "Authentication failed")
                    return
            
            try:
                if "id=" in query or "minecraft.net" in query:
                    extracted_id = extract_id_from_url(query)
                    if extracted_id:
                        result = PlayFab.main([extracted_id])
                        items = list(result.values()) if result else []
                        response_data = {
                            "success": True,
                            "data": items,
                            "total": len(items),
                            "query": query,
                            "search_type": "uuid"
                        }
                    else:
                        response_data = {
                            "success": True,
                            "data": [],
                            "total": 0,
                            "query": query,
                            "search_type": "uuid"
                        }
                
                elif re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', query.strip()):
                    result = PlayFab.main([query.strip()])
                    items = list(result.values()) if result else []
                    response_data = {
                        "success": True,
                        "data": items,
                        "total": len(items),
                        "query": query,
                        "search_type": "uuid"
                    }
                
                else:
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
                    
                    response_data = {
                        "success": True,
                        "data": items[:limit],
                        "total": len(items),
                        "query": query,
                        "search_type": search_type
                    }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                self.end_headers()
                
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as e:
                self.send_error(500, f"Search failed: {str(e)}")
                
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/api/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {"status": "healthy", "version": "1.0", "service": "MarkPE API"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")
