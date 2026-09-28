import os
import urllib.request
import urllib.parse
import re
import base64
import json
import time  # Added to handle rate-limiting delays

# --- CLOUDFLARE CONFIGURATION ---
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID", "your_account_id_here")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID", "your_kv_namespace_id_here")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN", "your_cloudflare_api_token_here")

# Pulls the active API endpoint address dynamically from your runner configuration environment
CF_BASE_API_URL = os.environ.get("CF_BASE_API_URL", "https://cloudflare.com").rstrip('/')

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google; +http://google.com)",
    "Accept": "application/xml,text/xml,*/*",
    "Connection": "keep-alive"
}

# The clean master feed link structure
p_url = "https" + ":" + "/" + "/" + "www" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/new" + "/" + ".rss"


def extract_and_decode_base64(xml_text):
    """
    Scans the thread XML content for Base64 text blocks and decodes them.
    """
    b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
    candidates = re.findall(b64_pattern, xml_text)
    
    decoded_results = []
    for candidate in candidates:
        if len(candidate) > 500:
            continue
            
        try:
            decoded_bytes = base64.b64decode(candidate, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='strict')
            
            if any(char.isalnum() for char in decoded_str):
                decoded_results.append((candidate, decoded_str))
        except Exception:
            continue
            
    return decoded_results


def write_to_cloudflare_kv(key, value):
    """
    Pushes data directly into your Cloudflare KV Namespace using environment-aligned URLs.
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
    except Exception as e:
        print(f"    ⚠️ Cloudflare KV write failed for key {key}: {e}")
    return False


def fetch_with_retry(url, headers, max_retries=3, initial_delay=5):
    """
    Fetches a URL and handles HTTP 429 rate limits by waiting and retrying.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            response = urllib.request.urlopen(req, timeout=15)
            return response
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                print(f"⚠️ Hit HTTP 429 Rate Limit. Backing off for {delay} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            else:
                raise e
        except Exception as e:
            raise e


def main():
    print("===============================================")
    print("🚀 INITIALIZING LOOP ARCHITECTURE RENav v9.5")
    print(f"Master Extraction Link: {p_url}")
    print("===============================================")
    
    try:
        # Utilizing the new retry logic for the master RSS connection
        response = fetch_with_retry(p_url, RSS_HEADERS)
        with response:
            status = response.status
            if status != 200:
                print(f"❌ Master tracking node dropped: HTTP {status}")
                return
                
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            
            # 🔍 ID EXTRACTOR: Isolate the unique post tokens directly out of the feed strings
            post_tokens = re.findall(r'/comments/([A-Za-z0-9]{5,10})/', raw_xml_content)
            unique_tokens = list(set(post_tokens))
            
            print(f"Successfully discovered {len(unique_tokens)} active target threads.")
            print("Beginning automated inner loop deep verification phase via RSS...")
            print("===============================================")

            success_count = 0
            for i, token in enumerate(unique_tokens[:5]):
                
                thread_rss_url = "https" + ":" + "/" + "/" + "www" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/comments" + "/" + token + "/" + ".rss"
                
                print(f"[{i+1}/5] Fetching thread feed safely via RSS: {thread_rss_url}")
                
                try:
                    # Also utilize retry handling for individual threads to manage traffic gracefully
                    t_res = fetch_with_retry(thread_rss_url, RSS_HEADERS)
                    with t_res:
                        if t_res.status == 200:
                            print(f"    🎉 SUCCESS! Thread XML payload successfully acquired. Status: {t_res.status}")
                            
                            thread_xml = t_res.read().decode('utf-8', errors='ignore')
                            found_pairs = extract_and_decode_base64(thread_xml)
                            
                            if found_pairs:
                                print(f"    🔍 Discovered {len(found_pairs)} valid string profiles. Syncing with Cloudflare...")
                                for idx, (raw_b64, decoded_text) in enumerate(found_pairs):
                                    kv_key = f"reddit:{token}:item_{idx}"
                                    
                                    if write_to_cloudflare_kv(kv_key, decoded_text):
                                        print(f"       ✅ Saved to KV -> Key: {kv_key}")
                                    else:
                                        print(f"       ❌ KV Save Failed -> Key: {kv_key}")
                            else:
                                print("    ℹ️ Connection active, but no eligible string parameters found inside the data block.")
                                
                            success_count += 1
                        else:
                            print(f"    ❌ Thread endpoint rejected extraction. Status code: {t_res.status}")
                except Exception as t_err:
                    print(f"    ❌ Extraction sequence encountered an exception: {t_err}")

            print("===============================================")
            print("🎉 PROCESSING LOOP TERMINATED SUCCESSFULLY!")
            print(f"Total Threads Successfully Breached: {success_count}/5")
            print("===============================================")
            return

    except Exception as network_error:
        print(f"❌ Traversal configuration engine failed: {network_error}")
        return

if __name__ == "__main__":
    main()
