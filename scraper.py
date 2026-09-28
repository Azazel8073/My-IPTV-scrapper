import os
import urllib.request
import urllib.parse
import re
import base64
import json

# --- CONFIGURATION LOGIC ---
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID", "your_account_id_here")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID", "your_kv_namespace_id_here")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN", "your_cloudflare_api_token_here")

# Production API hostname route
CF_BASE_API_URL = "https://api.cloudflare.com"

# Crucial Custom User-Agent to bypass Reddit's 403 datacenter block
REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 AggregatorScraper/1.0"
}

PASTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,text/plain,*/*"
}


def extract_credentials_from_text(text):
    """
    Extracts explicit M3U server connection links.
    """
    pattern = r'https?://[A-Za-z0-9\.]+/get\.php\?username=[A-Za-z0-9_&\-=]+'
    found_links = re.findall(pattern, text)
    return [link.strip() for link in found_links]


def extract_and_decode_base64(content_string):
    """
    Locates base64 segments within post fields, translates them, and processes the downstream files.
    """
    b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
    candidates = re.findall(b64_pattern, content_string)
    
    extracted_credentials = []
    for candidate in candidates:
        if len(candidate) > 500:
            continue
            
        try:
            decoded_bytes = base64.b64decode(candidate, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='strict').strip()
            
            if decoded_str.startswith("http://") or decoded_str.startswith("https://"):
                if "paste.sh/" in decoded_str:
                    decoded_str = decoded_str.split('#')[0].rstrip('/') + '/raw'
                
                print(f"       🔗 Pulling credentials from target paste provider: {decoded_str}")
                try:
                    req = urllib.request.Request(decoded_str, headers=PASTE_HEADERS, method="GET")
                    with urllib.request.urlopen(req, timeout=10) as ext_res:
                        if ext_res.status == 200:
                            raw_payload = ext_res.read().decode('utf-8', errors='ignore')
                            links = extract_credentials_from_text(raw_payload)
                            if links:
                                print(f"          🎉 Extracted {len(links)} lines successfully.")
                                extracted_credentials.extend(links)
                except Exception as crawl_err:
                    print(f"          ❌ Paste link download error: {crawl_err}")
            else:
                links = extract_credentials_from_text(decoded_str)
                if links:
                    extracted_credentials.extend(links)
        except Exception:
            continue
            
    return list(set(extracted_credentials))


def write_to_cloudflare_kv(key, value):
    """
    Updates the Cloudflare KV database directly via the core REST route structure.
    """
    url = f"{CF_BASE_API_URL}/client/v4/accounts/{CF_ACCOUNT_ID}/kv/namespaces/{CF_NAMESPACE_ID}/values/{key}"
    
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain"
    }
    
    data = value.encode('utf-8')
    req = urllib.request.Request(url, headers=headers, data=data, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 201):
                return True
    except urllib.error.HTTPError as e:
        print(f"    ❌ Cloudflare KV API failure: HTTP Error {e.code}")
    except Exception as e:
        print(f"    ⚠️ Cloudflare KV write failed: {e}")
    return False


def get_reddit_json(target_url):
    """
    Queries Reddit's native JSON endpoint securely with standard browser request contexts.
    """
    req = urllib.request.Request(target_url, headers=REDDIT_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=15) as response:
        if response.status == 200:
            return json.loads(response.read().decode('utf-8'))
    raise Exception(f"Reddit data engine returned non-OK status: {response.status}")


def main():
    print("===============================================")
    print("🚀 INITIALIZING PIPELINE DISCOVERY ENGINE")
    print("Target Channel: /r/IPTV_ZONENEW via Native Data Route")
    print("===============================================")
    
    try:
        # Utilizing direct JSON parsing structures to completely bypass proxy dependence
        target_main_feed = "https://reddit.com"
        print("🔄 Pulling new master thread lists from target subreddit...")
        feed_data = get_reddit_json(target_main_feed)
        
        children = feed_data.get("data", {}).get("children", [])
        print(f"Successfully discovered {len(children)} active target threads.")
        print("Beginning credentials compilation phase...")
        print("===============================================")

        all_compiled_credentials = []

        # Step 2: Loop through discovered threads and read descriptions
        for i, post in enumerate(children):
            post_data = post.get("data", {})
            token = post_data.get("id", "")
            title = post_data.get("title", "")
            description_text = post_data.get("selftext", "")
            
            print(f"[{i+1}/{len(children)}] Processing Thread [{token}] - Title: {title[:30]}...")
            
            # Extract and decrypt from the text body field directly
            if description_text:
                found_credentials = extract_and_decode_base64(description_text)
                if found_credentials:
                    all_compiled_credentials.extend(found_credentials)
            
            # Fetch corresponding comments for hidden updates
            try:
                comments_url = f"https://reddit.com{token}.json"
                comments_data = get_reddit_json(comments_url)
                
                # Reddit comment responses return as a secondary index list object array
                if isinstance(comments_data, list) and len(comments_data) > 1:
                    comment_listings = comments_data[1].get("data", {}).get("children", [])
                    for comment_node in comment_listings:
                        comment_body = comment_node.get("data", {}).get("body", "")
                        if comment_body:
                            comment_creds = extract_and_decode_base64(comment_body)
                            if comment_creds:
                                all_compiled_credentials.extend(comment_creds)
            except Exception as e:
                print(f"      ⚠️ Comment pass skipped for thread {token}: {e}")
                continue

        all_compiled_credentials = list(set(all_compiled_credentials))

        print("===============================================")
        if all_compiled_credentials:
            print(f"Processing complete. Found {len(all_compiled_credentials)} credentials strings.")
            final_kv_payload = "\n".join(all_compiled_credentials)
            
            print("🔄 Syncing aggregated credentials database into Cloudflare [raw_credentials]...")
            if write_to_cloudflare_kv("raw_credentials", final_kv_payload):
                print("✅ Cloudflare KV target index updated successfully!")
            else:
                print("❌ Failed to push payload update to KV database namespace.")
        else:
            print("ℹ️ Scraping cycle complete. No active data strings located.")
        print("===============================================")
        return

    except Exception as general_error:
        print(f"❌ Execution stopped by pipeline failure: {general_error}")
        return


if __name__ == "__main__":
    main()
