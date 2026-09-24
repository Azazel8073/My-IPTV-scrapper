import os
import requests
import json
import base64
import re

# Configurations
SUBREDDIT_URL = "https://reddit.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Aggregator-Bot/1.0"

# Cloudflare Configuration Elements 
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

def is_base64(s):
    # Regex pattern to identify standard Base64 chunks inside text fields
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

    for post in posts:
        post_data = post.get("data", {})
        # Scan both titles and post body copy descriptions for raw strings
        content_pool = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
        
        # Split tokens to isolate clean Base64 candidates
        words = re.split(r'[\s\n\r|,]+', content_pool)
        for word in words:
            word = word.strip()
            if is_base64(word):
                decoded = decode_base64(word)
                if "username=" in decoded and "password=" in decoded:
                    # Isolate clean line links
                    links = re.findall(r'https?://[^\s]+', decoded)
                    for link in links:
                        if link not in discovered_urls:
                            discovered_urls.append(link)

    if not discovered_urls:
        print("No new valid credential blocks found in the latest posts.")
        return

    print(f"Successfully harvested {len(discovered_urls)} credentials. Synchronizing with Cloudflare KV...")
    
    # Compile the discovered URLs into a single string formatted line-by-line
    compiled_dump = "\n".join(discovered_urls)

    # Push directly to your Cloudflare KV key using the REST API
    kv_endpoint = f"https://cloudflare.com{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/plain"
    }

    kv_response = requests.put(kv_endpoint, headers=kv_headers, data=compiled_dump)
    
    if kv_response.status_code == 200:
        print("Success! Your Cloudflare KV database has been refreshed with the latest lines.")
    else:
        print(f"Failed sync operation: {kv_response.text}")

if __name__ == "__main__":
    main()
