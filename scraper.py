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

# STRICT OVERRIDE: Enforces direct endpoint path to prevent pipeline 301 loops completely
CF_BASE_API_URL = "https://cloudflare.com"

# REDDIT COMPLIANT AGENT: Format recommended by Reddit API guidelines to avoid hard bot blocks
REDDIT_BOT_HEADERS = {
    "User-Agent": "server:IPTV-Reddit-Sync-Aggregator:v10.2 (by /u/anonymous_worker)",
    "Accept": "application/xml,text/xml,text/plain,*/*",
    "Connection": "keep-alive"
}

# ALTERNATIVE CRAWLER SIGNATURE: Used strictly for external paste.sh document streaming
PASTE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/plain,*/*"
}

# FIXED: Shifted base address to legacy node to clear automated CDN edge blocks
p_url = "https://old.reddit.com"


def extract_credentials_from_text(text):
    """
    Extracts lines that fit the M3U server credential format.
    """
    pattern = r'https?://[A-Za-z0-9\.]+/get\.php\?username=[A-Za-z0-9_&\-=]+'
    found_links = re.findall(pattern, text)
    return [link.strip() for link in found_links]


def extract_and_decode_base64(xml_text):
    """
    Scans the text for Base64 blocks, decodes them, and resolves downstream URLs.
    """
    b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
    candidates = re.findall(b64_pattern, xml_text)
    
    extracted_credentials = []
    for candidate in candidates:
        if len(candidate) > 500:
            continue
            
        try:
            decoded_bytes = base64.b64decode(candidate, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='strict').strip()
            
            if decoded_str.startswith("http://") or decoded_str.startswith("https://"):
                # Clean and parse paste containers directly into clean text streams
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
    url = f"{CF_BASE_API_URL}/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_NAMESPACE_ID}/values/{key}"
    
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


def fetch_with_retry(url, headers, max_retries=3, initial_delay=5):
    """
    Fetches a URL and handles server-side challenges with systematic backoffs.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            response = urllib.request.urlopen(req, timeout=15)
            return response
        except urllib.error.HTTPError as e:
            if (e.code in (429, 403)) and attempt < max_retries - 1:
                print(f"⚠️ Hit Status {e.code}. Backing off for {delay} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                raise e
        except Exception as e:
            raise e


def main():
    print("===============================================")
    print("🚀 INITIALIZING LOOP ARCHITECTURE RENav v10.2")
    print(f"Master Extraction Link: {p_url}")
    print(f"Target KV API Gateway: {CF_BASE_API_URL}")
    print("===============================================")
    
    try:
        response = fetch_with_retry(p_url, REDDIT_BOT_HEADERS)
        with response:
            status = response.status
            if status != 200:
                print(f"❌ Master tracking node dropped: HTTP {status}")
                return
                
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            post_tokens = re.findall(r'/comments/([A-Za-z0-9]{5,10})/', raw_xml_content)
            unique_tokens = list(set(post_tokens))
            
            print(f"Successfully discovered {len(unique_tokens)} active target threads.")
            print("Beginning credentials compilation phase...")
            print("===============================================")

            all_compiled_credentials = []

            for i, token in enumerate(unique_tokens[:5]):
                # Shifted inner feed paths to legacy layout to remain unified
                thread_rss_url = f"https://reddit.com{token}/.rss"
                
                try:
                    t_res = fetch_with_retry(thread_rss_url, REDDIT_BOT_HEADERS)
                    with t_res:
                        if t_res.status == 200:
                            thread_xml = t_res.read().decode('utf-8', errors='ignore')
                            print(f"[{i+1}/5] Checking Thread [{token}]...")
                            
                            found_credentials = extract_and_decode_base64(thread_xml)
                            if found_credentials:
                                all_compiled_credentials.extend(found_credentials)
                except Exception as t_err:
                    print(f"    ❌ Extraction sequence for thread [{token}] hit an error: {t_err}")

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
