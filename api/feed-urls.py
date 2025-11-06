"""
Simple endpoint to list all feed URLs
"""

from http.server import BaseHTTPRequestHandler
import json

# Dealership names for URL generation
DEALERSHIPS = [
    "Napleton_Chevrolet_Buick_GMC",
    "Napleton_Ford_Columbus",
    "Napleton_Chevrolet_Columbus",
    "Napleton_Beaver_Dam_CDJR",
    "Napleton_Downtown_Chevrolet",
    "Napleton_Downtown_Buick_GMC",
    "Napleton_Downtown_Hyundai",
    "Genesis_of_Downtown_Chicago",
    "Napleton_Chevrolet_Saint_Charles",
    "Napleton_Buick_GMC"
]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        base_url = "https://napleton-feeds.vercel.app"
        
        feeds = {}
        for dealership in DEALERSHIPS:
            feeds[dealership] = {
                'facebook': f"{base_url}/feeds/{dealership}_Facebook_AIA.xml",
                'google': f"{base_url}/feeds/{dealership}_Google_VLA.xml"
            }
        
        response = {
            'status': 'success',
            'total_dealerships': len(DEALERSHIPS),
            'feeds': feeds
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
