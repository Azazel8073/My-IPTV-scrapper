import os
import urllib.request
import urllib.parse
import re
import html
import base64

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

cf_p1 = "https:" + "//" + "api."
cf_p2 = "cloudflare.com" + "/client" + "/v4" + "/accounts"
CF_MASTER_API_URL = cf_p1 + cf_p2

# ⚠️ DIRECT TARGET CONFIGURATION LAYER: Hardcoded directly to today's active thread page text stream
TARGET_THREAD_URL = "https://reddit.com"

def loose_base64_decode(text_chunk):
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', text_chunk)
    if len(cleaned) < 16:
        return ""
    try:
        padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
        return base64.b64decode(padded.encode('utf-8')).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_credentials_from_bulk(text):
    found = []
    links = re.findall(r'https?://[^\s\n\r"\'><]+', text)
    for link in links:
        link_clean = link.strip().replace('"', '').replace("'", "").replace('\\', '')
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
    print(f"Connecting directly to today's target thread path text layout stream: {TARGET_THREAD_URL}")
    status, raw_text_response = make_api_request(TARGET_THREAD_URL, {"User-Agent": USER_AGENT, "Accept": "*/*"})
    
    if status != 200:
        print(f"Direct connection to Reddit thread failed with HTTP {status}. Trying direct mirror link...")
        fallback_thread = "https://extranic.me"
        status, raw_text_response = make_api_request(fallback_thread, {"User-Agent": USER_AGENT})
        if status != 200:
            print("Error: Could not reach today's thread copy text page data stream.")
            return

    discovered_urls = []
    kv_endpoint = f"{CF_MASTER_API_URL}/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "text/plain"}

    # Pull active data list from your Cloudflare account database
    status, existing_kv_text = make_api_request(kv_endpoint, kv_headers)
    if status == 200:
        discovered_urls = [line.strip() for line in existing_kv_text.split("\n") if line.strip()]
        print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")

    # Convert escaped symbols cleanly back to clean text strings
    clean_text_pool = html.unescape(raw_text_response).replace('\\/', '/').replace('\\"', '"')

    # GLOBAL TOKEN EXTRACTOR: Scan today's thread content for any Base64 strings directly
    potential_tokens = re.findall(r'[A-Za-z0-9+/=]{24,120}', clean_text_pool)
    print(f"Ingested thread layout data copy. Checking {len(potential_tokens)} raw text tokens for active Base64...")

    for token in potential_tokens:
        decoded = loose_base64_decode(token)
        
        # Check if the decrypted token reveals a target paste service signature
        if decoded and ("paste" in decoded or "get.php" in decoded or "http" in decoded):
            paste_links = re.findall(r'https?://?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co/[^\s\n\r"\'><\\]+', decoded)
            
            for paste_url in paste_links:
                raw_url = paste_url.strip()
                if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                print(f"Found active paste vector payload link: {raw_url}")
                p_status, p_text = make_api_request(raw_url, {"User-Agent": USER_AGENT})
                if p_status == 200:
                    parsed_links = extract_credentials_from_bulk(p_text)
                    for target_link in parsed_links:
                        if target_link not in discovered_urls:
                            discovered_urls.append(target_link)
                            print(f"   [Successfully Aggregated New Key]: {target_link}")

            direct_links = extract_credentials_from_bulk(decoded)
            for d_link in direct_links:
                if d_link not in discovered_urls:
                    discovered_urls.append(d_link)
                    print(f"   [Successfully Aggregated Direct New Key]: {d_link}")

    # Step 3: Synchronize updates back up to Cloudflare KV Namespace key
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
