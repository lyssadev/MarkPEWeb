from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "status": "ok",
            "message": "MarkPE API is running",
            "environment_check": {
                "PLAYFAB_CUSTOM_ID": "SET" if os.getenv('PLAYFAB_CUSTOM_ID') else "NOT SET",
                "PLAYFAB_PLAYER_SECRET": "SET" if os.getenv('PLAYFAB_PLAYER_SECRET') else "NOT SET", 
                "MARKPE_API_KEY": "SET" if os.getenv('MARKPE_API_KEY') else "NOT SET"
            }
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
