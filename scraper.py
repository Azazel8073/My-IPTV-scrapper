import os
import urllib.request
import urllib.parse

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

# ⚠️ SUBREDDIT NAVIGATION STITCHING: Building our specific path map completely safely
protocol = "https"
domain = "://opnxng.com"
sub_path = "/r/IPTV_ZONENEW"

# BoB joins them perfectly: https://://opnxng.com/r/IPTV_ZONENEW
TARGET_SUBREDDIT_URL = protocol + "://" + domain + sub_path

def main():
    print("===============================================")
    print("🚀 BOB INITIALIZING SUBREDDIT NAV RUN v5.0")
    print(f"Targeting Subreddit Feed: {TARGET_SUBREDDIT_URL}")
    print("===============================================")
    
    req = urllib.request.Request(TARGET_SUBREDDIT_URL, headers=BROWSER_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status == 200:
                print("===============================================")
                print("🎉 SUCCESS! BOB HAS NAVIGATED TO THE SUBREDDIT FEED!")
                print(f"Subreddit Response Code: HTTP {status}")
                print("===============================================")
                return
            else:
                print(f"❌ Handshake succeeded but page rejected: HTTP {status}")
                return
    except Exception as network_error:
        print(f"❌ Navigation failed at the gate! Error text: {network_error}")
        return

if __name__ == "__main__":
    main()
