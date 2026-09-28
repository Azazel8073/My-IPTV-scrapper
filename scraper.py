import os
import urllib.request
import urllib.parse
import re
import base64
import json
import time

# --- CONFIGURATION LOGIC ---
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID", "your_account_id_here")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID", "your_kv_namespace_id_here")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN", "your_cloudflare_api_token_here")

# Production API Routing Subdomain from our workflow YAML file setup
CF_BASE_API_URL = os.environ.get("CF_BASE_API_URL", "https://cloudflare.com")

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
    Locates base64 segments within post fields, translates them, and processes downstream files.
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
                    url_base = decoded_str.split('#')[0]
                    decoded_str = url_base.rstrip('/') + '/raw'
                
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
    Updates your Cloudflare KV namespace using your exact API configuration path.
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


def get_reddit_json_via_anonymizer(target_url):
    """
    Bypasses datacenter 403 blocks by querying the data layer through a public bridge with robust retry loops.
    """
    encoded_target = urllib.parse.quote_plus(target_url)
    proxy_url = f"https://codetabs.com/v1/proxy?quest={encoded_target}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(proxy_url, headers=PASTE_HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    wrapper_data = json.loads(response.read().decode('utf-8'))
                    contents = wrapper_data.get("contents")
                    if isinstance(contents, str):
                        return json.loads(contents)
                    return contents
        except Exception as e:
            print(f"      ⚠️ Proxy link connection attempt {attempt + 1} lagged: {e}")
            time.sleep(2)
            
    raise Exception("Anonymizer proxy timed out completely after 3 retries.")


def main():
    print("===============================================")
    print("🚀 INITIALIZING PIPELINE DISCOVERY ENGINE")
    print("Target Channel: /r/IPTV_ZONENEW via Keyless Bridge")
    print("===============================================")
    
    try:
        target_main_feed = "https://reddit.com/r/IPTV_ZONENEW/new.json?limit=10"
        print("🔄 Requesting master channel registry data from proxy portal...")
        feed_data = get_reddit_json_via_anonymizer(target_main_feed)
        
        children = []
        if isinstance(feed_data, dict):
            children = feed_data.get("data", {}).get("children", [])
            
        print(f"Successfully discovered {len(children)} active target threads.")
        print("Beginning credentials compilation phase...")
        print("===============================================")

        all_compiled_credentials = []

        for i, post in enumerate(children):
            post_data = post.get("data", {})
            token = post_data.get("id", "")
            title = post_data.get("title", "")
            description_text = post_data.get("selftext", "")
            
            print(f"[{i+1}/{len(children)}] Processing Thread [{token}] - Title: {title[:30]}...")
            
            if description_text:
                found_credentials = extract_and_decode_base64(description_text)
                if found_credentials:
                    all_compiled_credentials.extend(found_credentials)
            
            try:
                comments_url = f"https://reddit.com/r/IPTV_ZONENEW/comments/{token}.json"
                comments_data = get_reddit_json_via_anonymizer(comments_url)
                
                # Check for two-element list layouts common to Reddit comment JSON arrays
                if isinstance(comments_data, list) and len(comments_data) > 1:
                    comment_root = comments_data[1] if isinstance(comments_data, list) else {}
                    comment_listings = comment_root.get("data", {}).get("children", []) if isinstance(comment_root, dict) else []
                    
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
