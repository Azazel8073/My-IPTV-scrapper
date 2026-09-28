import os
import requests
import base64
import re
import html
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Failover Proxy Pool targeting the pure, unfiltered main chronological feed
PROXIES = [
    "https://extranic.me",
    "https://ducks.party",
    "https://catsarch.com",
    "https://opnxng.com"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
BASE_API_URL = os.environ.get("CF_BASE_API_URL")

def loose_base64_decode(text_chunk):
    cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', text_chunk)
    if len(cleaned) < 16:
        return ""
    try:
        padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
        decoded_bytes = base64.b64decode(padded, validate=False)
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

def main():
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if not BASE_API_URL:
        print("Error: CF_BASE_API_URL variable is missing in the workflow environment.")
        return

    # 1. Grab the raw unfiltered sub front-page directly
    raw_html = ""
    for proxy_base in PROXIES:
        front_page_target = f"{proxy_base}/r/IPTV_ZONENEW"
        print(f"Connecting to raw front feed: {front_page_target}")
        try:
            headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
            res = session.get(front_page_target, headers=headers, timeout=15)
            if res.status_code == 200 and "post_container" in res.text:
                raw_html = res.text
                print(f"Success! Pulled raw layout stream from: {proxy_base}")
                break
        except Exception:
            pass

    if not raw_html:
        print("Error: Proxy pool exhausted or unreachable.")
        return

    discovered_urls = []
    kv_endpoint = f"{BASE_API_URL}/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "text/plain"}

    try:
        existing_kv = session.get(kv_endpoint, headers=kv_headers, timeout=15)
        if existing_kv.status_code == 200:
            discovered_urls = [line.strip() for line in existing_kv.text.split("\n") if line.strip()]
            print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")
    except Exception as e:
        print(f"KV initial loading skipped: {e}")

    # Decode HTML-escaped proxy codes back to plain-text instantly
    clean_html = html.unescape(raw_html)

    # Separate raw post cards inside the markup frame
    post_containers = re.findall(r'<div class="post_container">.*?</div>\s*</div>\s*</div>', clean_html, re.DOTALL)
    if not post_containers:
        post_containers = re.findall(r'<div class="post.*?">.*?</div>\s*</div>', clean_html, re.DOTALL)

    print(f"Parsing {len(post_containers)} recent community posts layout layers...")

    for block in post_containers:
        # Extract contiguous chunks matching potential base64 strings directly out of post body layers
        potential_blocks = re.findall(r'[A-Za-z0-9+/=]{24,}', block)
        
        for base64_chunk in potential_blocks:
            decoded = loose_base64_decode(base64_chunk)
            
            # If the decoded string reveals any of our target paste targets
            if decoded and ("paste" in decoded or "get.php" in decoded):
                paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                
                for paste_url in paste_links:
                    raw_url = paste_url.strip()
                    if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                    if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                    print(f"Targeting hidden payload URL link: {raw_url}")
                    try:
                        paste_res = session.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=12)
                        if paste_res.status_code == 200:
                            parsed_links = extract_credentials_from_bulk(paste_res.text)
                            for target_link in parsed_links:
                                if target_link not in discovered_urls:
                                    discovered_urls.append(target_link)
                                    print(f"   [Successfully Appended]: {target_link}")
                    except Exception as p_err:
                        print(f"Failed loading contents from paste destination: {p_err}")

                direct_links = extract_credentials_from_bulk(decoded)
                for d_link in direct_links:
                    if d_link not in discovered_urls:
                        discovered_urls.append(d_link)
                        print(f"   [Successfully Appended Direct Link]: {d_link}")

    # 3. Synchronize aggregated configurations back to your account storage space
    if len(discovered_urls) > 0:
        compiled_dump = "\n".join(discovered_urls)
        try:
            kv_response = session.put(kv_endpoint, headers=kv_headers, data=compiled_dump, timeout=15)
            if kv_response.status_code == 200:
                print(f"Success! Sync completed. Current pool size: {len(discovered_urls)} lines.")
            else:
                print(f"Failed sync package delivery: {kv_response.text}")
        except Exception as put_err:
            print(f"Network write error: {put_err}")
    else:
        print("No unique credentials isolated during this tracking phase.")

if __name__ == "__main__":
    main()
