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
    # Matches common Base64 formats securely
    return bool(re.match(r'^[A-Za-z0-9+/=]{20,}$', s))

def decode_base64(data_string):
    try:
        return base64.b64decode(data_string).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_credentials_from_text(text):
    """Helper to parse raw lines containing username/password links out of a bulk text block"""
    found = []
    links = re.findall(r'https?://[^\s\n\r]+', text)
    for link in links:
        link_clean = link.strip().replace('"', '').replace("'", "")
        if "username=" in link_clean and "password=" in link_clean:
            if link_clean not in found:
                found.append(link_clean)
    return found

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
    kv_endpoint = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/plain"
    }

    try:
        existing_kv_response = requests.get(kv_endpoint, headers=kv_headers)
        if existing_kv_response.status_code == 200:
            discovered_urls = [line.strip() for line in existing_kv_response.text.split("\n") if line.strip()]
            print(f"Loaded {len(discovered_urls)} existing active lines from Cloudflare KV.")
    except Exception as e:
        print(f"KV read checkpoint skipped: {e}")

    # 2. Extract and decode Base64 strings to hunt for hidden paste URLs
    for post in posts:
        post_data = post.get("data", {})
        content_pool = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
        
        words = re.split(r'[\s\n\r|,]+', content_pool)
        for word in words:
            word = word.strip()
            if is_base64(word):
                decoded_text = decode_base64(word)
                
                # Check if the decoded block contains a secondary paste service link
                paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r]+', decoded_text)
                
                for paste_url in paste_links:
                    # Normalize common paste links to pull raw text output directly
                    raw_paste_url = paste_url.strip()
                    if "paste.sh/" in raw_paste_url and "/raw/" not in raw_paste_url:
                        raw_paste_url = raw_paste_url.replace("paste.sh/", "paste.sh/raw/")
                    if "://pastebin.com" in raw_paste_url and "/raw/" not in raw_paste_url:
                        raw_paste_url = raw_paste_url.replace("://pastebin.com", "://pastebin.comraw/")
                    
                    print(f"Found hidden paste vector! Fetching raw contents from: {raw_paste_url}")
                    try:
                        paste_res = requests.get(raw_paste_url, headers={"User-Agent": USER_AGENT}, timeout=8)
                        if paste_res.status_code == 200:
                            # Harvest the credentials hidden inside the paste text file
                            new_creds = extract_credentials_from_text(paste_res.text)
                            for cred in new_creds:
                                if cred not in discovered_urls:
                                    discovered_urls.append(cred)
                                    print(f"-> Harvested link: {cred}")
                    except Exception as paste_err:
                        print(f"Could not read stream from paste address node: {paste_err}")

                # Backup Check: If they pasted raw credentials directly into the base64 string without a paste link
                direct_creds = extract_credentials_from_text(decoded_text)
                for cred in direct_creds:
                    if cred not in discovered_urls:
                        discovered_urls.append(creed)

    if not discovered_urls:
        print("No new unique credential blocks found in the latest posts.")
        return

    print(f"Total compiled pool size: {len(discovered_urls)} lines. Pushing updates back to database pipeline...")
    
    # 3. Synchronize the expanded pool back to your database namespace key
    compiled_dump = "\n".join(discovered_urls)
    kv_response = requests.put(kv_endpoint, headers=kv_headers, data=compiled_dump)
    
    if kv_response.status_code == 200:
        print("Success! Your Cloudflare KV database has been updated with the appended paste lines.")
    else:
        print(f"Failed sync operation: {kv_response.text}")

if __name__ == "__main__":
    main()
