#!/usr/bin/env python3
"""
Generate feeds locally and save to feeds/ directory
Runs in GitHub Actions environment
"""

import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import paramiko
import os
from datetime import datetime
import tempfile
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

# SFTP Configuration from environment
SFTP_CONFIG = {
    'host': os.environ.get('SFTP_HOST'),
    'username': os.environ.get('SFTP_USERNAME'),
    'password': os.environ.get('SFTP_PASSWORD'),
    'directory': os.environ.get('SFTP_DIRECTORY', '/Vincue')
}

# Output directory
FEED_DIR = 'feeds'

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
        'store_code': '7093661331809096168'
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


def map_body_style(body_style_value):
    """Map CSV body style values to Google VLA accepted values"""
    if not body_style_value:
        return None
    
    normalized = body_style_value.lower().strip()
    
    body_style_mapping = {
        'suv': 'suv', 'sport utility': 'suv', 'crossover': 'crossover',
        'sedan': 'sedan', 'coupe': 'coupe', 'hatchback': 'hatchback',
        'wagon': 'station wagon', 'convertible': 'convertible',
        'truck': 'truck', 'pickup': 'truck', 'van': 'full size van',
        'minivan': 'minivan',
    }
    
    if normalized in body_style_mapping:
        return body_style_mapping[normalized]
    
    if 'suv' in normalized:
        return 'suv'
    if 'truck' in normalized:
        return 'truck'
    if 'van' in normalized:
        return 'minivan' if 'mini' in normalized else 'full size van'
    
    return None


def ensure_store_placeholder(url):
    """Ensure URL contains store placeholder"""
    if not url:
        return url
    placeholder = '{store_code}'
    parsed = urlparse(url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    
    if not any(k == 'store' for k, v in query_items):
        query_items.append(('store', placeholder))
    
    new_query = urlencode(query_items)
    result_url = urlunparse(parsed._replace(query=new_query))
    
    if new_query and not result_url.endswith('&'):
        result_url += '&'
    
    return result_url


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
        
        photos = parse_photos(vehicle.get('PhotoURL', ''))
        for photo_url in photos[:20]:
            ET.SubElement(listing, 'image').text = photo_url
    
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


G_NAMESPACE = 'http://base.google.com/ns/1.0'

def _add_g_element(parent, tag, text=None):
    element = ET.SubElement(parent, f"{{{G_NAMESPACE}}}{tag}")
    if text is not None:
        element.text = text
    return element


def generate_google_feed(vehicles, dealership, dealer_id):
    """Generate Google VLA feed"""
    root = ET.Element('feed', {
        'xmlns': 'http://www.w3.org/2005/Atom',
        'xmlns:g': G_NAMESPACE
    })

    ET.SubElement(root, 'title').text = f"{dealership['name']} Inventory Feed"
    ET.SubElement(root, 'link', {'href': dealership['website'], 'rel': 'self'})
    ET.SubElement(root, 'updated').text = datetime.now().isoformat()

    for vehicle in vehicles:
        vin = (vehicle.get('VIN') or '').strip()
        if not vin:
            continue

        condition_raw = (vehicle.get('New/Used') or '').upper()
        condition = 'new' if condition_raw == 'N' else ('certified' if condition_raw == 'C' else 'used')
        
        selling_price = clean_price(vehicle.get('PRICE'))
        msrp_price = clean_price(vehicle.get('MSRP'))
        
        if not selling_price and not msrp_price:
            continue
        if condition == 'new' and not msrp_price:
            continue
        
        primary_price = selling_price or msrp_price

        entry = ET.SubElement(root, 'entry')
        ET.SubElement(entry, 'id').text = vehicle.get('StockNo') or vin
        
        title = f"{vehicle.get('Year', '')} {vehicle.get('Make', '')} {vehicle.get('Model', '')}".strip()
        ET.SubElement(entry, 'title').text = title

        url = vehicle.get('VDPURL') or f"{dealership['website']}/inventory/details/{vin}"
        ET.SubElement(entry, 'link', {'rel': 'alternate', 'href': url})

        _add_g_element(entry, 'price', f"{primary_price:.2f} USD")
        _add_g_element(entry, 'vin', vin)
        _add_g_element(entry, 'condition', condition)
        _add_g_element(entry, 'availability', 'in stock')

        if msrp_price and (condition == 'new' or (selling_price and msrp_price != selling_price)):
            _add_g_element(entry, 'vehicle_msrp', f"{msrp_price:.2f} USD")

        photos = parse_photos(vehicle.get('PhotoURL', ''))
        if photos:
            _add_g_element(entry, 'image_link', photos[0])

    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def download_from_sftp():
    """Download inventory from SFTP"""
    print(f"Connecting to SFTP: {SFTP_CONFIG['host']}")
    transport = paramiko.Transport((SFTP_CONFIG['host'], 22))
    transport.connect(username=SFTP_CONFIG['username'], password=SFTP_CONFIG['password'])
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    try:
        sftp.chdir(SFTP_CONFIG['directory'])
        files = [f for f in sftp.listdir() if f.endswith('.csv')]
        if not files:
            raise Exception("No CSV files found")
        
        print(f"Found CSV file: {files[0]}")
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv') as tmp:
            sftp.get(files[0], tmp.name)
            return tmp.name
    finally:
        sftp.close()
        transport.close()


def process_inventory(csv_file):
    """Process inventory by dealership"""
    dealership_vehicles = {dealer_id: [] for dealer_id in DEALERSHIPS.keys()}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dealer_id = row.get('DealerID', '').strip()
            if dealer_id in DEALERSHIPS:
                dealership_vehicles[dealer_id].append(row)
    
    return dealership_vehicles


def main():
    print("Starting feed generation...")
    
    # Create feeds directory
    os.makedirs(FEED_DIR, exist_ok=True)
    
    # Download inventory
    csv_file = download_from_sftp()
    
    # Process inventory
    dealership_vehicles = process_inventory(csv_file)
    total_vehicles = sum(len(v) for v in dealership_vehicles.values())
    print(f"Processed {total_vehicles} vehicles across {len(dealership_vehicles)} dealerships")
    
    # Generate feeds
    for dealer_id, vehicles in dealership_vehicles.items():
        if not vehicles:
            continue
        
        dealership = DEALERSHIPS[dealer_id]
        dealer_name_safe = dealership['name'].replace(' ', '_').replace('/', '_')
        
        print(f"Generating feeds for {dealership['name']} ({len(vehicles)} vehicles)...")
        
        # Facebook feed
        fb_feed = generate_facebook_feed(vehicles, dealership)
        fb_path = os.path.join(FEED_DIR, f"{dealer_name_safe}_Facebook_AIA.xml")
        with open(fb_path, 'w', encoding='utf-8') as f:
            f.write(fb_feed)
        print(f"  ✓ {fb_path}")
        
        # Google feed
        google_feed = generate_google_feed(vehicles, dealership, dealer_id)
        google_path = os.path.join(FEED_DIR, f"{dealer_name_safe}_Google_VLA.xml")
        with open(google_path, 'w', encoding='utf-8') as f:
            f.write(google_feed)
        print(f"  ✓ {google_path}")
    
    # Cleanup
    os.unlink(csv_file)
    
    print("\n✓ Feed generation complete!")
    print(f"  Total vehicles: {total_vehicles}")
    print(f"  Feeds location: {FEED_DIR}/")


if __name__ == '__main__':
    main()
