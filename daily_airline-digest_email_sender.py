#!/usr/bin/env python3
import os
import sys
import json
import random
from datetime import datetime

# ============================================================================
# CONFIGURABLE DATA DIRECTORY (for persistent storage in ACI)
# ============================================================================
DATA_DIR = os.environ.get('DATA_DIR', '.')  # Default to current directory
SENT_FILE = os.path.join(DATA_DIR, "sent_airlines.json")

# Ensure the directory exists (in case it's a mounted volume)
os.makedirs(DATA_DIR, exist_ok=True)

# ============================================================================
# IMPORTS – assume packages installed in the environment
# ============================================================================
print("[INIT] Starting imports...")
try:
    import requests
    from amadeus import Client, ResponseError
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("")
    print("=" * 60)
    print("SOLUTION: Install required packages")
    print("=" * 60)
    sys.exit(1)

# ============================================================================
# CONFIGURATION – Load from environment variables
# ============================================================================
def load_config():
    """Load all secrets from environment variables."""
    print("[CONFIG] Loading configuration...")
    config = {
        'NINJAS_API_KEY': os.environ.get('NINJAS_API_KEY'),
        'AMADEUS_CLIENT_ID': os.environ.get('AMADEUS_CLIENT_ID'),
        'AMADEUS_CLIENT_SECRET': os.environ.get('AMADEUS_CLIENT_SECRET'),
        'SENDER_EMAIL': os.environ.get('SENDER_EMAIL'),
        'SENDER_APP_PASSWORD': os.environ.get('SENDER_APP_PASSWORD'),
        'RECIPIENT_EMAILS': os.environ.get('RECIPIENT_EMAILS', '')
    }

    # Parse recipients (comma-separated)
    if config['RECIPIENT_EMAILS']:
        emails = [e.strip() for e in config['RECIPIENT_EMAILS'].split(',') if e.strip()]
        config['RECIPIENT_EMAILS'] = emails
        print(f"[CONFIG] Recipients: {len(emails)}")
    else:
        config['RECIPIENT_EMAILS'] = []
        print("[CONFIG] WARNING: No recipients set")

    required = ['NINJAS_API_KEY', 'AMADEUS_CLIENT_ID', 'AMADEUS_CLIENT_SECRET',
                'SENDER_EMAIL', 'SENDER_APP_PASSWORD']
    missing = [var for var in required if not config[var]]
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        return None
    print("[CONFIG] Configuration loaded")
    return config

# ============================================================================
# LOCAL JSON STORAGE – using configurable path
# ============================================================================
def get_sent_airlines():
    """Read sent airlines from local JSON file."""
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE, 'r') as f:
                data = json.load(f)
                sent_set = set(data.get('sent', []))
                print(f"[STORAGE] Loaded {len(sent_set)} previously sent airlines from {SENT_FILE}")
                return sent_set
    except Exception as e:
        print(f"[STORAGE] Error reading file: {e}")
    print("[STORAGE] Starting fresh (no file or empty)")
    return set()

def add_sent_airline(iata_code, airline_name):
    """Add a new airline to the local JSON file."""
    try:
        sent_set = get_sent_airlines()
        sent_set.add(iata_code)
        with open(SENT_FILE, 'w') as f:
            json.dump({
                'sent': list(sent_set),
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
        print(f"[STORAGE] Added {iata_code} ({airline_name}) to {SENT_FILE}. Total: {len(sent_set)}")
        return True
    except Exception as e:
        print(f"[STORAGE] Error writing file: {e}")
        return False

# ============================================================================
# AIRLINE DATA FUNCTIONS (unchanged)
# ============================================================================
def get_random_airline(api_key):
    """Fetch a random airline from API-Ninjas."""
    print("[API] Fetching random airline...")
    url = "https://api.api-ninjas.com/v1/airlines"
    headers = {'X-Api-Key': api_key}
    try:
        response = requests.get(url, headers=headers, params={'name': 'a'}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            airline = random.choice(data)
            print(f"[API] Selected: {airline.get('name')} ({airline.get('iata')})")
            return airline
        print("[API] No data returned")
        return None
    except Exception as e:
        print(f"[API] Error: {e}")
        return None

def get_destinations(amadeus_client, airline_iata):
    """Fetch destinations for an airline using Amadeus."""
    if not airline_iata or len(airline_iata) != 2:
        return []
    print(f"[AMADEUS] Fetching destinations for {airline_iata}...")
    try:
        response = amadeus_client.airline.destinations.get(airlineCode=airline_iata)
        destinations = response.data if hasattr(response, 'data') else []
        if destinations:
            print(f"[AMADEUS] Found {len(destinations)} destinations")
        else:
            print("[AMADEUS] No destination data")
        return destinations
    except ResponseError:
        return []
    except Exception as e:
        print(f"[AMADEUS] Error: {e}")
        return []

# ============================================================================
# EMAIL FUNCTIONS (unchanged – create_email_content and send_email_bcc)
# ============================================================================
def create_email_content(airline_data, destinations):
    """Generate HTML email with airline facts, logo, fleet, and enhanced destinations."""
    airline_name = airline_data.get('name', 'Unknown')
    logo_url = airline_data.get('logo_url', '')
    logo_html = f'<img src="{logo_url}" style="max-height:80px; max-width:200px;">' if logo_url else ''

    fleet = airline_data.get('fleet', {})
    fleet_html = '<br>'.join([f"{k}: {v}" for k, v in fleet.items() if k != 'total']) or 'No detailed fleet data'
    total_aircraft = fleet.get('total', 'N/A')

    # --- DESTINATION PARSING (NO LIMIT) ---
    dest_html = ''
    valid_dests = []
    if destinations:
        for d in destinations:  # Removed the [:15] slice
            # Extract airport code (IATA)
            airport_code = d.get('iataCode')
            if not airport_code:
                continue

            # City name is at top-level 'name'
            city_name = d.get('name', 'Unknown')
            
            # Country code is inside the 'address' object
            address = d.get('address', {})
            country_code = address.get('countryCode', '??')

            display = f"{airport_code} – {city_name}, {country_code}"
            valid_dests.append(display)

    if valid_dests:
        # Split into two columns for a cleaner layout (even with many entries)
        mid = (len(valid_dests) + 1) // 2
        col1 = '<br>'.join(valid_dests[:mid])
        col2 = '<br>'.join(valid_dests[mid:]) if valid_dests[mid:] else ''
        
        dest_html = f"""
        <div style="background:#e8f4fc; padding:15px; border-radius:8px; margin:15px 0;">
            <h3 style="color:#2980b9;">🌍 Destination Airports</h3>
            <div style="display:flex;">
                <div style="flex:1; padding-right:10px;">{col1}</div>
                <div style="flex:1;">{col2}</div>
            </div>
            <p style="font-size:0.85em; color:#666; margin-top:10px;">
                Showing all {len(valid_dests)} airports served by {airline_name}.
            </p>
        </div>
        """

    # Full HTML email (unchanged)
    html = f"""
    <html>
    <body style="font-family:Arial, sans-serif; max-width:650px; margin:auto; color:#333;">
        <div style="background:linear-gradient(135deg,#1e3c72,#2a5298); padding:20px; color:white; border-radius:10px 10px 0 0;">
            <h1>✈️ Daily Airline Discovery</h1>
            <p>{datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        <div style="padding:25px; border:1px solid #ddd; border-top:none; border-radius:0 0 10px 10px;">
            <div style="text-align:center; margin-bottom:20px;">
                {logo_html}
                <h2>{airline_name}</h2>
                <p>IATA: {airline_data.get('iata','N/A')} | Founded: {airline_data.get('year_created','N/A')} | Country: {airline_data.get('country','N/A')}</p>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:15px; margin-bottom:20px;">
                <div style="flex:1; min-width:250px; background:#f8f9fa; padding:15px; border-radius:8px;">
                    <h3 style="color:#16a085;">📊 Core Facts</h3>
                    <p><strong>Base:</strong> {airline_data.get('base','N/A')}</p>
                    <p><strong>ICAO:</strong> {airline_data.get('icao','N/A')}</p>
                </div>
                <div style="flex:1; min-width:250px; background:#f8f9fa; padding:15px; border-radius:8px;">
                    <h3 style="color:#e74c3c;">✈️ Fleet Overview</h3>
                    <p>{fleet_html}</p>
                    <p><strong>Total Aircraft:</strong> {total_aircraft}</p>
                </div>
            </div>
            {dest_html}
            <div style="font-size:0.8em; color:#95a5a6; text-align:center; margin-top:25px; padding-top:15px; border-top:1px solid #eee;">
                <p>Data sources: API-Ninjas (airlines) • Amadeus (destinations)</p>
                <p>Automated daily service</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html, airline_name, len(valid_dests)

import requests  # Make sure this is at the top of your script (already there)

import requests  # Already at top

import os
import requests

def send_email_bcc(html_content, subject, sender_email, sender_password, recipients):
    """
    Send email via Mailgun REST API (EU region) with a friendly sender name.
    'sender_password' must be your Mailgun API key (starts with 'key-').
    The sender name can be customized via the environment variable SENDER_NAME.
    """
    if not recipients:
        print("[EMAIL] No recipients – skipping")
        return False

    print(f"[EMAIL] Sending to {len(recipients)} recipient(s) via Mailgun API...")
    try:
        # --- YOUR SPECIFIC CONFIGURATION ---
        mailgun_domain = 'mail.osys.sr'
        url = f'https://api.eu.mailgun.net/v3/{mailgun_domain}/messages'
        # -----------------------------------

        # Build a friendly "From" header
        sender_display = os.environ.get('SENDER_NAME', 'Daily Airline')
        from_header = f'"{sender_display}" <{sender_email}>'

        data = {
            'from': from_header,
            'to': [sender_email],          # 'to' is required; we set it to sender to avoid duplicate
            'bcc': recipients,              # List of hidden recipients
            'subject': subject,
            'html': html_content
        }

        response = requests.post(
            url,
            auth=('api', sender_password),   # sender_password = API key
            data=data,
            timeout=30
        )

        if response.status_code == 200:
            print("[EMAIL] Sent successfully via API")
            return True
        else:
            print(f"[EMAIL] API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[EMAIL] Exception: {e}")
        return False

def fetch_all_airlines(api_key):
    """Fetch all airlines by searching for each letter A-Z and deduplicating."""
    all_airlines = []
    seen_iata = set()
    base_url = "https://api.api-ninjas.com/v1/airlines"
    headers = {'X-Api-Key': api_key}
    
    # Loop through A-Z (both uppercase and lowercase work; API is case‑insensitive)
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        try:
            params = {'name': letter}
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            airlines = response.json()
            
            for airline in airlines:
                iata = airline.get('iata')
                # Only add if it has a valid IATA and we haven't seen it before
                if iata and iata not in seen_iata:
                    seen_iata.add(iata)
                    all_airlines.append(airline)
            
            print(f"[MAIN] Letter {letter}: found {len(airlines)} airlines, {len(all_airlines)} unique so far")
            
            # Optional: small delay to avoid hitting rate limits
            # time.sleep(0.1)
            
        except Exception as e:
            print(f"[MAIN] Warning: failed to fetch for letter {letter}: {e}")
            continue
    
    print(f"[MAIN] Total unique airlines with IATA codes: {len(all_airlines)}")
    return all_airlines
    
# ============================================================================
# MAIN EXECUTION
# ============================================================================
def fetch_all_airlines(api_key):
    """
    Fetch all airlines from API-Ninjas by searching each letter A-Z.
    Returns a list of unique airline dictionaries that have a valid IATA code.
    """
    all_airlines = []
    seen_iata = set()
    base_url = "https://api.api-ninjas.com/v1/airlines"
    headers = {'X-Api-Key': api_key}
    
    print("[FETCH] Starting full airline fetch (A-Z)...")
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        try:
            params = {'name': letter}
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            airlines = response.json()
            
            for airline in airlines:
                iata = airline.get('iata')
                # Only include airlines with a valid IATA code and not already seen
                if iata and iata not in seen_iata:
                    seen_iata.add(iata)
                    all_airlines.append(airline)
            
            print(f"[FETCH] Letter {letter}: found {len(airlines)} airlines, total unique: {len(all_airlines)}")
            
            # Optional: tiny delay to be gentle to the API
            # time.sleep(0.05)
            
        except Exception as e:
            print(f"[FETCH] Warning: failed to fetch for letter {letter}: {e}")
            continue
    
    print(f"[FETCH] Completed. Total unique airlines with IATA codes: {len(all_airlines)}")
    return all_airlines


def main():
    print("\n" + "="*60)
    print(f"Daily Airline Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    config = load_config()
    if not config:
        return 1

    # Get already sent airlines from local JSON
    sent_airlines = get_sent_airlines()
    print(f"[MAIN] Already sent: {len(sent_airlines)} airlines")

    # Fetch complete list of airlines (searching A-Z)
    all_airlines = fetch_all_airlines(config['NINJAS_API_KEY'])
    if not all_airlines:
        print("[MAIN] ❌ Failed to retrieve any airlines")
        return 1

    # Filter out airlines that are already sent or missing IATA (already filtered in fetch)
    available_airlines = [a for a in all_airlines if a.get('iata') not in sent_airlines]

    if not available_airlines:
        print("[MAIN] ❌ No new airlines available (all have been sent or lack IATA codes).")
        print("[MAIN] Consider resetting sent_airlines.json or expanding the data source.")
        return 1

    # Randomly pick one airline from the available ones
    airline = random.choice(available_airlines)
    iata = airline.get('iata')
    airline_name = airline.get('name', 'Unknown')
    print(f"[MAIN] ✅ Selected new airline: {airline_name} ({iata})")

    # Get destinations from Amadeus
    amadeus = Client(
        client_id=config['AMADEUS_CLIENT_ID'],
        client_secret=config['AMADEUS_CLIENT_SECRET']
    )
    destinations = get_destinations(amadeus, iata)

    # Create email content
    html, airline_name, dest_count = create_email_content(airline, destinations)

    # Send email
    subject = f"✈️ Daily Airline: {airline_name}"
    email_sent = send_email_bcc(
        html, subject,
        config['SENDER_EMAIL'],
        config['SENDER_APP_PASSWORD'],
        config['RECIPIENT_EMAILS']
    )

    if not email_sent:
        print("[MAIN] ❌ Email failed – not updating sent list")
        return 1

    # Update local JSON file
    update_ok = add_sent_airline(iata, airline_name)

    if update_ok:
        print("\n" + "="*60)
        print("✅ SUCCESS! Daily airline email completed.")
        print(f"   Airline: {airline_name}")
        print(f"   Destinations shown: {dest_count}")
        print("="*60)
        return 0
    else:
        print("\n" + "!"*60)
        print("⚠️  WARNING: Email sent but file update failed.")
        print("   This airline may be repeated in the future.")
        print("!"*60)
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)