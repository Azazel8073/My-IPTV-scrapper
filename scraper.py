import os
import urllib.request
import urllib.parse
import re
import base64  # Added for decoding
import json    # Added for formatting Cloudflare API payloads

# --- CLOUDFLARE CONFIGURATION ---
# Replace these with your actual Cloudflare credentials or environment variables
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "your_account_id_here")
CF_NAMESPACE_ID = os.environ.get("CF_NAMESPACE_ID", "your_kv_namespace_id_here")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "your_cloudflare_api_token_here")

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google; +http://google.com)",
    "Accept": "application/xml,text/xml,*/*",
    "Connection": "keep-alive"
}

# The clean master feed link structure
p_url = "https" + ":" + "/" + "/" + "www" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/new" + "/" + ".rss"


def extract_and_decode_base64(html_text):
    """
    Scans the thread text for potential Base64 strings, validates, and decodes them.
    """
    # Regex to find standard Base64 patterns (letters, numbers, +, /, and optional = padding)
    # Looking for strings that are at least 16 characters long to avoid false positives
    b64_pattern = r'[A-Za-z0-9+/]{16,}={0,2}'
    candidates = re.findall(b64_pattern, html_text)
    
    decoded_results = []
    for candidate in candidates:
        # Avoid processing massive blocks of layout text or standard HTML attributes
        if len(candidate) > 500:
            continue
            
        try:
            # Attempt to decode the string
            decoded_bytes = base64.b64decode(candidate, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='strict')
            
            # Simple check to ensure the decoded string looks like readable text/data
            if any(char.isalnum() for char in decoded_str):
                decoded_results.append((candidate, decoded_str))
        except Exception:
            # If it throws an error, it wasn't valid Base64 data; skip it safely
            continue
            
    return decoded_results


def write_to_cloudflare_kv(key, value):
    """
    Pushes a key-value pair directly into your Cloudflare KV Namespace using native urllib.
    """
    url = f"https://cloudflare.com{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_NAMESPACE_ID}/values/{key}"
    
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain"  # Cloudflare KV values are sent as plain text or stringified JSON
    }
    
    # Cloudflare expects the raw value string encoded into bytes for the PUT request
    data = value.encode('utf-8')
    
    req = urllib.request.Request(url, headers=headers, data=data, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 201):
                return True
    except Exception as e:
        print(f"    ⚠️ Cloudflare KV write failed for key {key}: {e}")
    return False


def main():
    print("===============================================")
    print("🚀 INITIALIZING LOOP ARCHITECTURE RENav v9.2")
    print(f"Master Extraction Link: {p_url}")
    print("===============================================")
    
    req = urllib.request.Request(p_url, headers=RSS_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status != 200:
                print(f"❌ Master tracking node dropped: HTTP {status}")
                return
                
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            
            # 🔍 ID EXTRACTOR: Isolate the unique 7-character post tokens directly out of the feed strings
            post_tokens = re.findall(r'/comments/([A-Za-z0-9]{5,10})/', raw_xml_content)
            unique_tokens = list(set(post_tokens))
            
            print(f"Successfully discovered {len(unique_tokens)} active target threads.")
            print("Beginning automated inner loop deep verification phase...")
            print("===============================================")

            success_count = 0
            # Sifting through the newest 5 targets to keep our connection test blazing fast
            for i, token in enumerate(unique_tokens[:5]):
                
                # ⚠️ EXPLICIT LINK BUILDER: Completely ignores the old domain and builds a fresh 'old.reddit' address path natively
                old_reddit_url = "https" + ":" + "/" + "/" + "old" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/comments" + "/" + token + "/"
                
                print(f"[{i+1}/5] Deep navigating straight into thread: {old_reddit_url}")
                
                # High-authentication desktop browser layout headers to fully bypass the 403 block
                browser_handshake_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Cache-Control": "max-age=0",
                    "Connection": "close"
                }
                
                t_req = urllib.request.Request(old_reddit_url, headers=browser_handshake_headers, method="GET")
                try:
                    with urllib.request.urlopen(t_req, timeout=12) as t_res:
                        if t_res.status == 200:
                            print(f"    🎉 SUCCESS! Healthy connection established with post page text. Status: {t_res.status}")
                            
                            # READ THE PAGE DATA
                            thread_html = t_res.read().decode('utf-8', errors='ignore')
                            
                            # SCAN AND DECODE BASE64 STRINGS
                            found_pairs = extract_and_decode_base64(thread_html)
                            
                            if found_pairs:
                                print(f"    🔍 Found {len(found_pairs)} valid Base64 string(s). Synchronizing to Cloudflare...")
                                for idx, (raw_b64, decoded_text) in enumerate(found_pairs):
                                    # Create a unique KV key using the thread token and an incrementing index
                                    kv_key = f"reddit:{token}:item_{idx}"
                                    
                                    # Sync to Cloudflare
                                    if write_to_cloudflare_kv(kv_key, decoded_text):
                                        print(f"       ✅ Saved to KV -> Key: {kv_key}")
                                    else:
                                        print(f"       ❌ KV Save Failed -> Key: {kv_key}")
                            else:
                                print("    ℹ️ No valid Base64 text blobs matched inside this thread.")
                                
                            success_count += 1
                        else:
                            print(f"    ❌ Handshake established but thread data page rejected code: {t_res.status}")
                except Exception as t_err:
                    print(f"    ❌ Connection failed to thread endpoint: {t_err}")

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
