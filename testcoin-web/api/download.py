import json
import hashlib
import time
from http.server import BaseHTTPRequestHandler
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Testcoin'))

try:
    import PlayFab
except ImportError:
    PlayFab = None

API_KEYS = {
    hashlib.sha256("markpe_api_key_2024".encode()).hexdigest(): "internal"
}

download_cooldowns = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path != '/api/download':
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
            
            item_id = request_data.get('item_id', '').strip()
            
            if not item_id:
                self.send_error(400, "item_id is required")
                return
            
            client_ip = self.headers.get('X-Forwarded-For', self.client_address[0])
            current_time = time.time()
            
            if client_ip in download_cooldowns:
                time_since_last = current_time - download_cooldowns[client_ip]
                if time_since_last < 30:
                    remaining = int(30 - time_since_last)
                    self.send_error(429, f"Rate limit exceeded. Try again in {remaining} seconds")
                    return
            
            download_cooldowns[client_ip] = current_time
            
            if not PlayFab:
                self.send_error(500, "PlayFab module not available")
                return
            
            try:
                result = PlayFab.main([item_id])
                
                if not result or item_id not in result:
                    self.send_error(404, "Content not found")
                    return
                
                content_data = result[item_id]
                
                if not content_data or 'download_url' not in content_data:
                    self.send_error(404, "Download URL not available")
                    return
                
                import requests
                download_url = content_data['download_url']
                
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                
                filename = f"{content_data.get('title', 'content').replace(' ', '_')}.zip"
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                self.end_headers()
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)
                
            except Exception as e:
                self.send_error(500, f"Download failed: {str(e)}")
                
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
