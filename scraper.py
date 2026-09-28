import os
import urllib.request
import urllib.parse

# BoB's Pristine Browser Identity Configuration Map
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

# ⚠️ STATIC HANDSHAKE ENGINE: Broken into bare words to prevent mobile clipboard slash-injection bugs
protocol = "https"
slashes = ":" + "//"
domain = "://opnxng.com"

# BoB stitches it perfectly on launch: https://://opnxng.com
STATIC_TEST_URL = protocol + slashes + domain

def main():
    print("===============================================")
    print("🚀 BOB INITIALIZING HANDSHAKE STEP RUN v4.0")
    print(f"Targeting Static Gateway: {STATIC_TEST_URL}")
    print("===============================================")
    
    req = urllib.request.Request(STATIC_TEST_URL, headers=BROWSER_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status == 200:
                print("===============================================")
                print("🎉 SUCCESS! BOB HAS ESTABLISHED A HEALTHY HANDSHAKE!")
                print(f"Response Code from Proxy Node: HTTP {status}")
                print("===============================================")
                return
            else:
                print(f"❌ Connection initialized but handshake rejected: HTTP {status}")
                return
    except Exception as network_error:
        print(f"❌ Handshake failed at the gate! Error text: {network_error}")
        return

if __name__ == "__main__":
    main()
