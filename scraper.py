import os
import urllib.request
import urllib.parse

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,*/*",
    "Connection": "keep-alive"
}

# ⚠️ HIGH-AVAILABILITY CLOUDFLARE GATEWAY LAYER: Complete open path whitelisted inside GitHub cloud networks
protocol = "https"
domain = "api.pullreddit.workers.dev"
sub_path = "/r/IPTV_ZONENEW/new.json"

# Stitched cleanly with zero punctuation formatting overlaps or trailing artifacts
TARGET_SUBREDDIT_URL = protocol + "://" + domain + sub_path

def main():
    print("===============================================")
    print("🚀 BOB INITIALIZING SUBREDDIT NAV RUN v5.2")
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
                print(f"❌ Handshake succeeded but gateway rejected: HTTP {status}")
                return
    except Exception as network_error:
        print(f"❌ Navigation failed at the gate! Error text: {network_error}")
        return

if __name__ == "__main__":
    main()
