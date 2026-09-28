import os
import requests
import base64
import re
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# ⚠️ PROXY IMPLEMENTATION VECTOR: Bypasses rate blocks by pulling text layout frames from an open proxy node
p1 = "https:" + "//" + "redlib.extranic.me"
p2 = "/r" + "/" + "IPTV" + "_ZONE" + "NEW" + "/search"
p3 = "?q=" + "paste" + "&sort=new&t=all"

REDLIB_SEARCH_URL = p1 + p2 + p3
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
    retry_strategy = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if not BASE_API_URL:
        print("Error: CF_BASE_API_URL variable is missing in the workflow environment.")
        return

    print(f"Connecting to open-source content stream mirror proxy node: {REDLIB_SEARCH_URL}")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = session.get(REDLIB_SEARCH_URL, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Proxy bridge connection rejected: HTTP {response.status_code}")
            return
    except Exception as err:
        print(f"Failed establishing bridge network path: {err}")
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

    # Isolate specific content block containers mapped by Redlib layout architectures
    raw_html = response.text
    post_containers = re.findall(r'<div class="post_container">.*?</div>\s*</div>\s*</div>', raw_html, re.DOTALL)
    
    # Fallback pattern if container classes are wrapped uniquely
    if not post_containers:
        post_containers = re.findall(r'<div class="post.*?">.*?</div>\s*</div>', raw_html, re.DOTALL)

    print(f"Proxy successfully served {len(post_containers)} raw un-cached community layers.")

    for block in post_containers:
        # Scan everything inside the post element container for continuous base64 code string characters
        potential_blocks = re.findall(r'[A-Za-z0-9+/=]{24,}', block)
        
        for base64_chunk in potential_blocks:
            decoded = loose_base64_decode(base64_chunk)
            if not decoded or "paste" not in decoded:
                continue

            # Extract the embedded paste destination urls from the layout map
            paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
            for paste_url in paste_links:
                raw_url = paste_url.strip()
                if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                print(f"Found paste link vector: {raw_url}")
                try:
                    paste_res = session.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=10)
                    if paste_res.status_code == 200:
                        parsed_links = extract_credentials_from_bulk(paste_res.text)
                        for target_link in parsed_links:
                            if target_link not in discovered_urls:
                                discovered_urls.append(target_link)
                                print(f"-> Harvested: {target_link}")
                except Exception as p_err:
                    print(f"Failed loading contents from paste destination: {p_err}")

            direct_links = extract_credentials_from_bulk(decoded)
            for d_link in direct_links:
                if d_link not in discovered_urls:
                    discovered_urls.append(d_link)
                    print(f"-> Harvested (Direct): {d_link}")

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
