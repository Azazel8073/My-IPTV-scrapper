import os
import urllib.request
import urllib.parse
import re
import html
import base64

# A pristine, complete browser profile identity to guarantee handshake approvals
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# The single thread destination we are testing our network handshake against
TARGET_THREAD_URL = "https://reddit.com"

def main():
    print(f"Initiating network handshake sequence to: {TARGET_THREAD_URL}")
    
    req = urllib.request.Request(TARGET_THREAD_URL, headers=BROWSER_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            
            # If the server responds with a valid success block code (HTTP 200)
            if status == 200:
                print("===============================================")
                print("🎉 HEALTHY CONNECTION HANDSHAKE ESTABLISHED WITH REDDIT!")
                print(f"Response Code: HTTP {status}")
                print("===============================================")
                
                # Download a small snippet of the page text to verify it's reading real data
                sample_data = response.read(1000).decode('utf-8', errors='ignore')
                print(f"Data verification checkpoint size: {len(sample_data)} characters read.")
                return
            else:
                print(f"❌ Connection initialized but handshake rejected: HTTP {status}")
                return
                
    except Exception as network_error:
        print(f"❌ Handshake failed at the gate! Network connection dropped. Error: {network_error}")
        return

if __name__ == "__main__":
    main()
