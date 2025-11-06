"""
Simple test endpoint to verify Vercel Python is working
"""

from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'success',
            'message': 'Vercel Python is working!',
            'timestamp': datetime.now().isoformat()
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
