import os
import urllib.request
import urllib.parse
import re
import base64
import json
import time

# --- CLOUDFLARE CONFIGURATION ---
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID", "your_account_id_here")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID", "your_kv_namespace_id_here")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN", "your_cloudflare_api_token_here")

# Force direct gateway to completely drop Cloudflare 301 loop errors
CF_BASE_API_URL = "https://api.cloudflare.com"

# Generic request context headers for external paste crawling blocks
PASTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,text/plain,*/*"
}


def extract_credentials_from_text(text):
    """
    Extracts lines that fit the M3U server credential format.
    """
    pattern = r'https?://[A-Za-z0-9\.]+/get\.php\?username=[A-Za-z0-9_&\-=]+'
    found_links = re.findall(pattern, text)
    return [link.strip() for link in found_links]


def extract_and_decode_base64(content_string):
    """
    Scans free text fields for Base64 blocks, decodes them, and resolves paste configurations.
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
                    decoded_str = decoded_str.split('#')[0]
                    decoded_str = decoded_str.rstrip('/') + '/raw'
                
                print(f"       🔗 Crawling Target Data Endpoint: {decoded_str}")
                try:
                    req = urllib.request.Request(decoded_str, headers=PASTE_HEADERS, method="GET")
                    with urllib.request.urlopen(req, timeout=10) as ext_res:
                        if ext_res.status == 200:
                            raw_payload = ext_res.read().decode('utf-8', errors='ignore')
                            links = extract_credentials_from_text(raw_payload)
                            if links:
                                print(f"          🎉 Extracted {len(links)} credential entries from link.")
                                extracted_credentials.extend(links)
                except Exception as crawl_err:
                    print(f"          ❌ Data link extraction failed: {crawl_err}")
            else:
                links = extract_credentials_from_text(decoded_str)
                if links:
                    extracted_credentials.extend(links)
        except Exception:
            continue
            
    return list(set(extracted_credentials))


def write_to_cloudflare_kv(key, value):
    """
    Pushes data directly into your Cloudflare KV Namespace.
    """
    # FIXED: Structurally aligned API endpoint routing URL path according to API reference
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
        print(f"    ❌ Cloudflare KV write failed for key {key}: HTTP Error {e.code}")
    except Exception as e:
        print(f"    ⚠️ Cloudflare KV write failed for key {key}: {e}")
    return False


def get_json_via_proxy(target_rss_url):
    """
    Fetches Reddit RSS feeds safely converted into structured JSON blocks using an open API proxy gateway.
    """
    encoded_url = urllib.parse.quote_plus(target_rss_url)
    
    # FIXED: Added correct query argument syntax separation to prevent nonnumeric port errors
    proxy_gateway_url = f"https://rss2json.com{encoded_url}"
    
    req = urllib.request.Request(proxy_gateway_url, headers=PASTE_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=15) as response:
        if response.status == 200:
            return json.loads(response.read().decode('utf-8'))
    raise Exception(f"Proxy engine rejected operation with status: {response.status}")


def main():
    print("===============================================")
    print("🚀 INITIALIZING LOOP ARCHITECTURE RENav v10.3")
    print("Target Channel: /r/IPTV_ZONENEW via RSS Proxy")
    print(f"Target KV API Gateway: {CF_BASE_API_URL}")
    print("===============================================")
    
    try:
        # FIXED: Targets the structured RSS endpoint directly instead of an raw unparseable HTML landing page
        target_main_feed = "https://reddit.com"
        print("🔄 Requesting master channel registry data from proxy portal...")
        feed_data = get_json_via_proxy(target_main_feed)
        
        items = feed_data.get("items", [])
        print(f"Successfully discovered {len(items)} active target threads.")
        print("Beginning credentials compilation phase...")
        print("===============================================")

        all_compiled_credentials = []

        # Step 2: Loop through discovered threads and pull post inner content blocks
        for i, item in enumerate(items[:5]):
            thread_link = item.get("link", "")
            # Extract out the comments token identifier
            token_match = re.search(r'/comments/([A-Za-z0-9]{5,10})/', thread_link)
            
            if token_match:
                token = token_match.group(1)
                print(f"[{i+1}/5] Checking Thread [{token}] via data properties...")
                
                # Check text body fields directly supplied by the conversion layer
                content_snippet = item.get("content", "") + " " + item.get("description", "")
                
                found_credentials = extract_and_decode_base64(content_snippet)
                if found_credentials:
                    all_compiled_credentials.extend(found_credentials)
                    
                # Fetch the thread's distinct feed directly via the proxy portal
                try:
                    thread_rss_url = f"https://reddit.com{token}/.rss"
                    thread_data = get_json_via_proxy(thread_rss_url)
                    for comment in thread_data.get("items", []):
                        comment_text = comment.get("content", "") + " " + comment.get("description", "")
                        comment_creds = extract_and_decode_base64(comment_text)
                        if comment_creds:
                            all_compiled_credentials.extend(comment_creds)
                except Exception:
                    # Skip secondary extraction failures gracefully if individual threads throw issues
                    continue

        all_compiled_credentials = list(set(all_compiled_credentials))

        print("===============================================")
        if all_compiled_credentials:
            print(f"Processing complete. Found {len(all_compiled_credentials)} total credentials.")
            final_kv_payload = "\n".join(all_compiled_credentials)
            
            print("🔄 Syncing global aggregated data into [raw_credentials]...")
            if write_to_cloudflare_kv("raw_credentials", final_kv_payload):
                print("✅ [raw_credentials] updated successfully!")
            else:
                print("❌ Failed to push update to [raw_credentials]")
        else:
            print("ℹ️ Finished pass. No new clean credential strings found.")
        print("===============================================")
        return

    except Exception as network_error:
        print(f"❌ Traversal configuration engine failed: {network_error}")
        return

if __name__ == "__main__":
    main()
