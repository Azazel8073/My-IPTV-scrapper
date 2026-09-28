import os
import urllib.request
import urllib.parse
import json
import base64
import re
import html

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

cf_p1 = "https:" + "//" + "api."
cf_p2 = "cloudflare.com" + "/client" + "/v4" + "/accounts"
CF_MASTER_API_URL = cf_p1 + cf_p2

# High-availability proxy pool targets to avoid reddit rate blocks
BACKUP_FEEDS = [
    "https://extranic.me",
    "https://workers.dev",
    "https://opnxng.com"
]

def loose_base64_decode(text_chunk):
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', text_chunk)
    if len(cleaned) < 16:
        return ""
    try:
        padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
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
    # Step 1: Connect to high-availability data stream mirrors natively
    raw_text_payload = ""
    active_feed_base = ""
    for target_feed in BACKUP_FEEDS:
        print(f"Connecting to data pipeline endpoint: {target_feed}")
        reddit_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        status, text_response = make_api_request(target_feed, reddit_headers)
        
        if status == 200 and len(text_response) > 100:
            raw_text_payload = text_response
            # FIXED LOGIC: Correctly extracted netloc layout component string parameters
            parsed_uri = urllib.parse.urlparse(target_feed)
            active_feed_base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
            print(f"Success! Pulled raw layout text stream via: {target_feed}")
            break

    if not raw_text_payload:
        print("Error: All primary and fallback data streams are currently unreachable.")
        return

    discovered_urls = []
    kv_endpoint = f"{CF_MASTER_API_URL}/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "text/plain"}

    status, existing_kv_text = make_api_request(kv_endpoint, kv_headers)
    if status == 200:
        discovered_urls = [line.strip() for line in existing_kv_text.split("\n") if line.strip()]
        print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")

    clean_search_text = html.unescape(raw_text_payload)

    # ACCURATE PATH RESOLVER: Harvests the unique post ID tokens directly from both raw proxy paths and json feeds
    post_ids = re.findall(r'/(?:comments|p)/([A-Za-z0-9]{4,12})', clean_search_text)
    if not post_ids:
        post_ids = re.findall(r'href="/r/IPTV_ZONENEW/(?:comments|p)?/?([A-Za-z0-9]{4,12})', clean_search_text)
        
    post_ids = list(set([pid for pid in post_ids if pid not in ["search", "new", "hot", "top", "about", "styles"]]))
    
    # Rebuild explicit direct URLs to navigate into each thread's separate deep text data
    target_thread_urls = [f"{active_feed_base}/r/IPTV_ZONENEW/comments/{pid}/" for pid in post_ids]
    print(f"Dynamic mapping analyzer successfully isolated {len(target_thread_urls)} individual thread targets to process.")

    # Step 2: Navigate inside each specific post link sequentially to scan the complete uncut body text
    for thread_url in target_thread_urls:
        print(f"Entering deep thread endpoint context: {thread_url}")
        t_status, t_html = make_api_request(thread_url, {"User-Agent": USER_AGENT})
        if t_status != 200:
            continue
            
        clean_thread_html = html.unescape(t_html)
        
        # Strip structural HTML noise formatting elements to prevent broken or clipped base64 blocks
        text_without_html_tags = re.sub(r'<[^>]*>', ' ', clean_thread_html)
        
        # Universal lookahead regex scans strings for potential base64 layouts blocks
        potential_blocks = re.findall(r'[A-Za-z0-9+/=\s\n\r]{24,}', text_without_html_tags)
        
        for chunk_with_spaces in potential_blocks:
            decoded = loose_base64_decode(chunk_with_spaces)
            
            if decoded and ("paste" in decoded or "get.php" in decoded or "http" in decoded):
                paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                
                for paste_url in paste_links:
                    raw_url = paste_url.strip()
                    if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                    if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                    print(f"   -> Found hidden paste payload: {raw_url}")
                    p_status, p_text = make_api_request(raw_url, {"User-Agent": USER_AGENT})
                    
                    if p_status == 200:
                        parsed_links = extract_credentials_from_bulk(p_text)
                        for target_link in parsed_links:
                            if target_link not in discovered_urls:
                                discovered_urls.append(target_link)
                                print(f"      [Successfully Appended]: {target_link}")

                direct_links = extract_credentials_from_bulk(decoded)
                for d_link in direct_links:
                    if d_link not in discovered_urls:
                        discovered_urls.append(d_link)
                        print(f"      [Successfully Appended Direct]: {d_link}")

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
