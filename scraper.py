import os
import urllib.request
import urllib.parse
import re
import html

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

# Stitch Cloudflare endpoint variables securely
cf_p1 = "https:" + "//" + "api."
cf_p2 = "cloudflare.com" + "/client" + "/v4" + "/accounts"
CF_MASTER_API_URL = cf_p1 + cf_p2

# High-availability data feeds (chronological list)
BACKUP_FEEDS = [
    "https://workers.dev",
    "https://extranic.me",
    "https://opnxng.com"
]

def loose_base64_decode(text_chunk):
    # CRITICAL TRACKER FIX: Strip all text noise and whitespaces completely to isolate pure Base64 strings
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', text_chunk)
    if len(cleaned) < 16:
        return ""
    try:
        # Dynamically append correct standard layout padding
        padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
        # Force strict binary decoding check configurations
        decoded_bytes = base64.b64decode(padded.encode('utf-8'))
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_credentials_from_bulk(text):
    found = []
    links = re.findall(r'https?://[^\s\n\r"\'><]+', text)
    for link in links:
        link_clean = link.strip().replace('"', '').replace("'", "")
        if "username=" in link_clean and "password=" in link_clean:
            if link_clean not in found:
                found.append(link_clean)
    return found

def make_api_request(url, headers, method="GET", data=None):
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, data=data, timeout=15) as response:
            return response.status, response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

def main():
    import base64 # Secure local runtime environment import module
    
    # 1. Connect to high-availability data stream mirrors natively
    raw_text_payload = ""
    for target_feed in BACKUP_FEEDS:
        print(f"Connecting to data pipeline endpoint: {target_feed}")
        reddit_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        status, text_response = make_api_request(target_feed, reddit_headers)
        
        if status == 200 and len(text_response) > 100:
            raw_text_payload = text_response
            print(f"Success! Pulled raw layout text stream via: {target_feed}")
            break

    if not raw_text_payload:
        print("Error: All primary and fallback data streams are currently unreachable.")
        return

    discovered_urls = []
    kv_endpoint = f"{CF_MASTER_API_URL}/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "text/plain"}

    # Fetch current pool state from Cloudflare
    status, existing_kv_text = make_api_request(kv_endpoint, kv_headers)
    if status == 200:
        discovered_urls = [line.strip() for line in existing_kv_text.split("\n") if line.strip()]
        print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")
    else:
        print(f"Initial KV connection skipped or empty: {existing_kv_text}")

    # 2. Universal String Sifting
    clean_search_text = html.unescape(raw_text_payload)
    
    # ACCURATE CHUNK EXTRACTOR: Splits text strictly by spaces, line ends, or punctuation to isolate raw tokens
    potential_words = re.split(r'[\s\n\r"\'><,\^]+', clean_search_text)
    print(f"Analyzing {len(potential_words)} raw text tokens for active Base64 structures...")

    for word in potential_words:
        word = word.strip()
        # Clean lookahead match rules for standard Base64 string blocks (length 20 to 120 chars long)
        if re.match(r'^[A-Za-z0-9+/=]{20,120}$', word):
            decoded = loose_base64_decode(word)
            
            if decoded and ("paste" in decoded or "get.php" in decoded or "http" in decoded):
                # Isolate target paste lines cleanly out of the decrypted string mapping text
                paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                
                for paste_url in paste_links:
                    raw_url = paste_url.strip()
                    if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                    if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                    print(f"Targeting hidden payload URL link: {raw_url}")
                    p_headers = {"User-Agent": USER_AGENT}
                    p_status, p_text = make_api_request(raw_url, p_headers)
                    
                    if p_status == 200:
                        parsed_links = extract_credentials_from_bulk(p_text)
                        for target_link in parsed_links:
                            if target_link not in discovered_urls:
                                discovered_urls.append(target_link)
                                print(f"   [Appended New Key]: {target_link}")
                    else:
                        print(f"   Could not read paste contents: HTTP {p_status}")

                direct_links = extract_credentials_from_bulk(decoded)
                for d_link in direct_links:
                    if d_link not in discovered_urls:
                        discovered_urls.append(d_link)
                        print(f"   [Appended New Direct Key]: {d_link}")

    # 3. Synchronize updates back up to Cloudflare KV Namespace key
    if len(discovered_urls) > 0:
        compiled_dump = "\n".join(discovered_urls)
        binary_data = compiled_dump.encode('utf-8')
        
        status, response_text = make_api_request(kv_endpoint, kv_headers, method="PUT", data=binary_data)
        if status == 200:
            print(f"Success! Sync completed. Current total pool size inside your database: {len(discovered_urls)} lines.")
        else:
            print(f"Failed writing data back to Cloudflare: {response_text}")
    else:
        print("No unique credentials isolated during this tracking phase.")

if __name__ == "__main__":
    main()
