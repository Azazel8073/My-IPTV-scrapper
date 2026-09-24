import os
import requests
import json
import base64
import re

# Configurations
SUBREDDIT_URL = "https://reddit.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Aggregator-Bot/1.0"

# Cloudflare Configuration Elements (Loaded securely via GitHub Secrets)
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

def is_base64(s):
    # Identifies standard Base64 chunks inside text fields (at least 20 chars long)
    return bool(re.match(r'^[A-Za-z0-9+/=]{20,}$', s))

def decode_base64(data_string):
    try:
        return base64.b64decode(data_string).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def main():
    print("Fetching recent data streams from r/IPTV_ZONENEW...")
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(SUBREDDIT_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed accessing Reddit target nodes: HTTP {response.status_code}")
        return

    data = response.json()
    posts = data.get("data", {}).get("children", [])
    
    discovered_urls = []

    # 1. Pull down any links currently stored in your KV store first to avoid overwriting
    kv_endpoint = f"https://cloudflare.com{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/plain"
    }

    try:
        existing_kv_response = requests.get(kv_endpoint, headers=kv_headers)
        if existing_kv_response.status_code == 200:
            # Populate our list with your existing lines so they remain protected
            discovered_urls = [line.strip() for line in existing_kv_response.text.split("\n") if line.strip()]
            print(f"Loaded {len(discovered_urls)} existing active lines from Cloudflare KV.")
    except Exception as e:
        print(f"KV read checkpoint skipped: {e}")

    # 2. Extract and decode the new Base64 strings from the subreddit
    for post in posts:
        post_data = post.get("data", {})
        content_pool = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
        
        words = re.split(r'[\s\n\r|,]+', content_pool)
        for word in words:
            word = word.strip()
            if is_base64(word):
                decoded = decode_base64(word)
                if "username=" in decoded and "password=" in decoded:
                    links = re.findall(r'https?://[^\s]+', decoded)
                    for link in links:
                        link_clean = link.strip()
                        # Deduplicate: only add the link if it doesn't already exist in your pool
                        if link_clean and link_clean not in discovered_urls:
                            discovered_urls.append(link_clean)

    if not discovered_urls:
        print("No new unique credential blocks found in the latest posts.")
        return

    print(f"Total compiled pool size: {len(discovered_urls)} lines. Pushing updates back to database pipeline...")
    
    # 3. Synchronize the expanded pool back to your database namespace key
    compiled_dump = "\n".join(discovered_urls)
    kv_response = requests.put(kv_endpoint, headers=kv_headers, data=compiled_dump)
    
    if kv_response.status_code == 200:
        print("Success! Your Cloudflare KV database has been updated with the appended lines.")
    else:
        print(f"Failed sync operation: {kv_response.text}")

if __name__ == "__main__":
    main()
