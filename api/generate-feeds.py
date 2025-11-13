"""
Vercel Serverless Function for Feed Generation with Blob Storage
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
import tempfile
import requests

# SFTP Configuration
SFTP_CONFIG = {
    'host': os.environ.get('SFTP_HOST', 'sparkling-water-50295.sftptogo.com'),
    'username': os.environ.get('SFTP_USERNAME', '9839656$fac1df083b674db747b667'),
    'password': os.environ.get('SFTP_PASSWORD', 'MWS7YFlGGlC4q73q2jGtsl4Bt7A2Fz'),
    'directory': os.environ.get('SFTP_DIRECTORY', '/Vincue')
}

# Vercel Blob Configuration
BLOB_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')

# Dealership Configuration
DEALERSHIPS = {
    '28685': {
        'name': 'Napleton Chevrolet Buick GMC',
        'website': 'https://www.napletonchevybuickgmc.com',
        'address': 'N8167 Kellom Rd., Beaver Dam, WI 53916',
        'store_code': '8769789203665249729'
    },
    '29312': {
        'name': 'Napleton Ford Columbus',
        'website': 'https://www.napletonfordcolumbus.com',
        'address': '330 Transit Rd., Columbus, WI 53925',
        'store_code': '5445979293761982858'
    },
    '148261': {
        'name': 'Napleton Chevrolet Columbus',
        'website': 'https://www.napletonchevycolumbus.com',
        'address': '800 Maple Avenue, Columbus, WI 53925',
        'store_code': '1647799517431806713'
    },
    '115908': {
        'name': 'Napleton Beaver Dam Chrysler Dodge Jeep Ram',
        'website': 'https://www.beaverdamcdjr.com/',
        'address': '1724 N Spring St., Beaver Dam, WI 53916',
        'store_code': '252221242249419797'
    },
    '50912': {
        'name': 'Napleton Downtown Chevrolet',
        'website': 'https://www.downtownchevy.com',
        'address': '2720 S. Michigan Ave., Chicago, IL 60616',
        'store_code': '7227908043401009324'
    },
    '216163': {
        'name': 'Napleton Downtown Buick GMC',
        'website': 'https://www.downtownbuickgmc.com',
        'address': '2720 S. Michigan Ave., Chicago, IL 60616',
        'store_code': '4088446453747783674'
    },
    '125848': {
        'name': 'Napleton Downtown Hyundai',
        'website': 'https://www.napletondowntownhyundai.com/',
        'address': '2700 S. Michigan Ave., Chicago, IL 60616',
        'store_code': '8954334598476874759'
    },
    '215614': {
        'name': 'Genesis of Downtown Chicago',
        'website': 'https://www.genesisofdowntownchicago.com/',
        'address': '2700 S. Michigan Ave., Chicago, IL 60616',
        'store_code': '3078858109013009292'
    },
    '4802': {
        'name': 'Napleton Chevrolet Saint Charles',
        'website': 'https://www.napletonchevrolet.com',
        'address': '2015 E. Main St., Saint Charles, IL 60174',
        'store_code': '7093661331809090000'
    },
    '30389': {
        'name': 'Napleton Buick GMC',
        'website': 'https://www.napletoncrystallake.com',
        'address': '6305 Northwest Hwy., Crystal Lake, IL 60014',
        'store_code': '30389'
    }
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


G_NAMESPACE = 'http://base.google.com/ns/1.0'


def _add_g_element(parent, tag, text=None, attrib=None):
    """Helper to add an element under the Google namespace"""
    element = ET.SubElement(parent, f"{{{G_NAMESPACE}}}{tag}", attrib or {})
    if text is not None:
        element.text = text
    return element


def generate_google_feed(vehicles, dealership, dealer_id):
    """Generate Google VLA feed"""
    root = ET.Element('feed', {
        'xmlns': 'http://www.w3.org/2005/Atom',
        'xmlns:g': 'http://base.google.com/ns/1.0'
    })

    ET.SubElement(root, 'title').text = f"{dealership['name']} Inventory Feed"
    ET.SubElement(root, 'link', {'href': dealership['website'], 'rel': 'self'})
    ET.SubElement(root, 'updated').text = datetime.now().isoformat()

    for vehicle in vehicles:
        vin = (vehicle.get('VIN') or '').strip()
        if not vin:
            # Skip vehicles without a VIN as they cannot be served in VLAs
            continue

        price = clean_price(vehicle.get('PRICE')) or clean_price(vehicle.get('MSRP'))
        if not price:
            # Skip vehicles without a valid price - Google requires price for VLAs
            continue

        entry = ET.SubElement(root, 'entry')
        ET.SubElement(entry, 'id').text = vin

        trim_value = (vehicle.get('Trim') or '').strip()
        if len(trim_value) > 150:
            trim_value = trim_value[:150]

        title_parts = [vehicle.get('Year', '').strip(), vehicle.get('Make', '').strip(), vehicle.get('Model', '').strip(), trim_value]
        title = " ".join(part for part in title_parts if part).strip()
        ET.SubElement(entry, 'title').text = title

        url = (vehicle.get('VDPURL') or '').strip() or f"{dealership['website']}/inventory/details/{vin}"
        ET.SubElement(entry, 'link', {'rel': 'alternate', 'href': url})

        # Required VLA fields
        _add_g_element(entry, 'id', vin)
        _add_g_element(entry, 'price', f"{price:.2f} USD")
        _add_g_element(entry, 'vin', vin)
        _add_g_element(entry, 'google_product_category', '916')
        _add_g_element(entry, 'brand', vehicle.get('Make', '').strip() or dealership['name'])

        # Store/Dealership information (required for VLA)
        _add_g_element(entry, 'store_code', dealership['store_code'])
        _add_g_element(entry, 'dealership_name', dealership['name'])
        _add_g_element(entry, 'dealership_address', dealership['address'])

        # Vehicle fulfillment - in-store pickup only (no shipping for vehicles)
        fulfillment = _add_g_element(entry, 'vehicle_fulfillment')
        _add_g_element(fulfillment, 'option', 'in_store')
        _add_g_element(fulfillment, 'store_code', dealership['store_code'])

        # Vehicle details
        if vehicle.get('Year'):
            _add_g_element(entry, 'year', vehicle['Year'].strip())
        if vehicle.get('Make'):
            _add_g_element(entry, 'make', vehicle['Make'].strip())
        if vehicle.get('Model'):
            _add_g_element(entry, 'model', vehicle['Model'].strip())

        condition_raw = (vehicle.get('New/Used') or '').upper()
        if condition_raw == 'N':
            condition = 'new'
        elif condition_raw == 'C':
            condition = 'certified'
        else:
            condition = 'used'
        _add_g_element(entry, 'condition', condition)
        _add_g_element(entry, 'availability', 'in stock')

        # VDP tracking templates
        _add_g_element(entry, 'link_template', url)

        # Optional fields
        if trim_value:
            _add_g_element(entry, 'trim', trim_value)

        miles_value = vehicle.get('Miles')
        if miles_value:
            try:
                mileage = int(float(miles_value))
                if mileage >= 0:
                    _add_g_element(entry, 'mileage', str(mileage), attrib={'unit': 'miles'})
            except Exception:
                pass

        if vehicle.get('Body'):
            _add_g_element(entry, 'body_style', vehicle['Body'].strip())

        if vehicle.get('ExteriorColor'):
            _add_g_element(entry, 'color', vehicle['ExteriorColor'].strip())

        # Images - First image is main image_link, rest are additional_image_link
        photos = parse_photos(vehicle.get('PhotoURL', ''))
        if photos:
            # Main image (required)
            _add_g_element(entry, 'image_link', photos[0])
            # Additional images (up to 9 more for total of 10)
            for photo_url in photos[1:10]:
                _add_g_element(entry, 'additional_image_link', photo_url)

    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def upload_to_blob(filename, content):
    """Upload content to Vercel Blob Storage"""
    if not BLOB_TOKEN:
        return None
    
    try:
        # Vercel Blob API endpoint
        url = f"https://blob.vercel-storage.com/{filename}"
        
        headers = {
            'Authorization': f'Bearer {BLOB_TOKEN}',
            'Content-Type': 'application/xml',
            'x-content-type': 'application/xml'
        }
        
        response = requests.put(url, data=content.encode('utf-8'), headers=headers)
        
        if response.status_code in [200, 201]:
            result = response.json()
            return result.get('url')
        else:
            print(f"Blob upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error uploading to blob: {e}")
        return None


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
            
            # Generate and upload feeds
            feeds_generated = []
            feed_urls = {}
            
            for dealer_id, vehicles in dealership_vehicles.items():
                if not vehicles:
                    continue

                dealership = DEALERSHIPS[dealer_id]
                dealer_name_safe = dealership['name'].replace(' ', '_').replace('/', '_')

                # Generate Facebook feed
                fb_feed = generate_facebook_feed(vehicles, dealership)
                fb_filename = f"{dealer_name_safe}_Facebook_AIA.xml"
                fb_url = upload_to_blob(fb_filename, fb_feed)

                # Generate Google feed
                google_feed = generate_google_feed(vehicles, dealership, dealer_id)
                google_filename = f"{dealer_name_safe}_Google_VLA.xml"
                google_url = upload_to_blob(google_filename, google_feed)
                
                feeds_generated.append({
                    'dealership': dealership['name'],
                    'dealer_id': dealer_id,
                    'vehicle_count': len(vehicles),
                    'facebook_feed_url': fb_url,
                    'google_feed_url': google_url
                })
                
                feed_urls[dealer_name_safe] = {
                    'facebook': fb_url,
                    'google': google_url
                }
            
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
                'feeds_generated': feeds_generated,
                'feed_urls': feed_urls
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
