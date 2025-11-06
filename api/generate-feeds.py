"""
Vercel Serverless Function for Feed Generation
Endpoint: /api/generate-feeds
"""

from http.server import BaseHTTPRequestHandler
import json
import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import paramiko
import os
from datetime import datetime
from io import StringIO
import tempfile

# SFTP Configuration - Use environment variables in production
SFTP_CONFIG = {
    'host': os.environ.get('SFTP_HOST', 'sparkling-water-50295.sftptogo.com'),
    'username': os.environ.get('SFTP_USERNAME', '9839656$fac1df083b674db747b667'),
    'password': os.environ.get('SFTP_PASSWORD', 'MWS7YFlGGlC4q73q2jGtsl4Bt7A2Fz'),
    'directory': os.environ.get('SFTP_DIRECTORY', '/Vincue')
}

# Dealership Configuration
DEALERSHIPS = {
    '28685': {'name': 'Napleton Chevrolet Buick GMC', 'website': 'https://www.napletonchevy.com'},
    '29312': {'name': 'Napleton Ford Columbus', 'website': 'https://www.napletonfordcolumbus.com'},
    '148261': {'name': 'Napleton Chevrolet Columbus', 'website': 'https://www.napletonchevy.com'},
    '115908': {'name': 'Napleton Beaver Dam CDJR', 'website': 'https://www.napletonbeaverdam.com'},
    '50912': {'name': 'Napleton Downtown Chevrolet', 'website': 'https://www.downtownchevy.com'},
    '216163': {'name': 'Napleton Downtown Buick GMC', 'website': 'https://www.napletondowntownbuickgmc.com'},
    '125848': {'name': 'Napleton Downtown Hyundai', 'website': 'https://www.napletondowntownhyundai.com'},
    '215614': {'name': 'Genesis of Downtown Chicago', 'website': 'https://www.genesisofdowntownchicago.com'},
    '4802': {'name': 'Napleton Chevrolet Saint Charles', 'website': 'https://www.napletonchevy.com'},
    '30389': {'name': 'Napleton Buick GMC', 'website': 'https://www.napletonbuickgmc.com'}
}


def clean_price(price_str):
    """Clean and format price value"""
    if not price_str or price_str == '0.00' or price_str == '0':
        return None
    try:
        return float(price_str.replace(',', ''))
    except:
        return None


def parse_photos(photo_url_string):
    """Parse pipe-separated photo URLs"""
    if not photo_url_string:
        return []
    return [url.strip() for url in photo_url_string.split('|') if url.strip()]


def generate_facebook_feed(vehicles, dealership):
    """Generate Facebook AIA feed"""
    root = ET.Element('listings')
    
    for vehicle in vehicles:
        listing = ET.SubElement(root, 'listing')
        ET.SubElement(listing, 'id').text = vehicle['VIN']
        ET.SubElement(listing, 'year').text = vehicle['Year']
        ET.SubElement(listing, 'make').text = vehicle['Make']
        ET.SubElement(listing, 'model').text = vehicle['Model']
        ET.SubElement(listing, 'vin').text = vehicle['VIN']
        ET.SubElement(listing, 'availability').text = 'in stock'
        
        price = clean_price(vehicle['PRICE']) or clean_price(vehicle['MSRP'])
        if price:
            ET.SubElement(listing, 'price').text = f"{price:.2f} USD"
        
        url = vehicle.get('VDPURL') or f"{dealership['website']}/inventory/details/{vehicle['VIN']}"
        ET.SubElement(listing, 'url').text = url
        
        condition = 'new' if vehicle.get('New/Used', '').upper() == 'N' else 'used'
        ET.SubElement(listing, 'condition').text = condition
        
        if vehicle.get('Miles'):
            try:
                ET.SubElement(listing, 'mileage').text = str(int(float(vehicle['Miles'])))
                ET.SubElement(listing, 'mileage_unit').text = 'mi'
            except:
                pass
        
        if vehicle.get('Trim'):
            ET.SubElement(listing, 'trim').text = vehicle['Trim']
        if vehicle.get('Body'):
            ET.SubElement(listing, 'body_style').text = vehicle['Body']
        if vehicle.get('ExteriorColor'):
            ET.SubElement(listing, 'exterior_color').text = vehicle['ExteriorColor']
        if vehicle.get('InteriorColor'):
            ET.SubElement(listing, 'interior_color').text = vehicle['InteriorColor']
        
        photos = parse_photos(vehicle.get('PhotoURL', ''))
        for photo_url in photos[:20]:
            ET.SubElement(listing, 'image').text = photo_url
    
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def generate_google_feed(vehicles, dealership):
    """Generate Google VLA feed"""
    root = ET.Element('feed', {
        'xmlns': 'http://www.w3.org/2005/Atom',
        'xmlns:g': 'http://base.google.com/ns/1.0'
    })
    
    ET.SubElement(root, 'title').text = f"{dealership['name']} Inventory Feed"
    ET.SubElement(root, 'link', {'href': dealership['website'], 'rel': 'self'})
    ET.SubElement(root, 'updated').text = datetime.now().isoformat()
    
    for vehicle in vehicles:
        entry = ET.SubElement(root, 'entry')
        ET.SubElement(entry, 'id').text = vehicle['VIN']
        ET.SubElement(entry, 'title').text = f"{vehicle['Year']} {vehicle['Make']} {vehicle['Model']} {vehicle.get('Trim', '')}".strip()
        
        url = vehicle.get('VDPURL') or f"{dealership['website']}/inventory/details/{vehicle['VIN']}"
        ET.SubElement(entry, 'link', {'href': url})
        
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}id').text = vehicle['VIN']
        
        price = clean_price(vehicle['PRICE']) or clean_price(vehicle['MSRP'])
        if price:
            ET.SubElement(entry, '{http://base.google.com/ns/1.0}price').text = f"{price:.2f} USD"
        
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}year').text = vehicle['Year']
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}make').text = vehicle['Make']
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}model').text = vehicle['Model']
        
        condition = 'new' if vehicle.get('New/Used', '').upper() == 'N' else 'used'
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}condition').text = condition
        ET.SubElement(entry, '{http://base.google.com/ns/1.0}availability').text = 'in stock'
        
        photos = parse_photos(vehicle.get('PhotoURL', ''))
        for photo_url in photos[:10]:
            ET.SubElement(entry, '{http://base.google.com/ns/1.0}image_link').text = photo_url
    
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def download_from_sftp():
    """Download inventory from SFTP"""
    transport = paramiko.Transport((SFTP_CONFIG['host'], 22))
    transport.connect(username=SFTP_CONFIG['username'], password=SFTP_CONFIG['password'])
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    try:
        sftp.chdir(SFTP_CONFIG['directory'])
        files = [f for f in sftp.listdir() if f.endswith('.csv')]
        if not files:
            raise Exception("No CSV files found")
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv') as tmp:
            sftp.get(files[0], tmp.name)
            return tmp.name
    finally:
        sftp.close()
        transport.close()


def process_inventory(csv_file):
    """Process inventory and split by dealership"""
    dealership_vehicles = {dealer_id: [] for dealer_id in DEALERSHIPS.keys()}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dealer_id = row.get('DealerID', '').strip()
            if dealer_id in DEALERSHIPS:
                dealership_vehicles[dealer_id].append(row)
    
    return dealership_vehicles


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Download inventory
            csv_file = download_from_sftp()
            
            # Process inventory
            dealership_vehicles = process_inventory(csv_file)
            
            # Generate feeds
            feeds_generated = []
            for dealer_id, vehicles in dealership_vehicles.items():
                if not vehicles:
                    continue
                
                dealership = DEALERSHIPS[dealer_id]
                
                # Generate Facebook feed
                fb_feed = generate_facebook_feed(vehicles, dealership)
                # In production, save to Vercel Blob Storage or S3
                
                # Generate Google feed
                google_feed = generate_google_feed(vehicles, dealership)
                # In production, save to Vercel Blob Storage or S3
                
                feeds_generated.append({
                    'dealership': dealership['name'],
                    'dealer_id': dealer_id,
                    'vehicle_count': len(vehicles)
                })
            
            # Clean up temp file
            os.unlink(csv_file)
            
            # Return success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'total_vehicles': sum(len(v) for v in dealership_vehicles.values()),
                'feeds_generated': feeds_generated
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            error_response = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(error_response, indent=2).encode())
