import os
import requests
import base64
import re
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# ⚠️ FIXED ENDPOINT VECTOR: Hitting the raw API JSON node forces Reddit to bypass all local caches
j1 = "https:" + "//" + "old."
j2 = "reddit.com" + "/r" + "/"
j3 = "IPTV" + "_ZONE" + "NEW" + "/"
j4 = "new" + ".json" + "?" + "sort=new&limit=25"

SUBREDDIT_JSON_URL = j1 + j2 + j3 + j4
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Parser-Engine/8.0"

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

    print(f"Connecting to raw API data pipeline: {SUBREDDIT_JSON_URL}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = session.get(SUBREDDIT_JSON_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Reddit API stream fetch failed: HTTP {response.status_code}")
            return
    except Exception as err:
        print(f"Failed connecting to server node: {err}")
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

    try:
        # Unpack the raw JSON data map safely
        payload = response.json()
        posts = payload.get("data", {}).get("children", [])
        print(f"Successfully retrieved the latest {len(posts)} active community threads.")

        for post in posts:
            post_data = post.get("data", {})
            title = post_data.get("title", "")
            body_text = post_data.get("selftext", "")
            
            # Combine both text layers to maximize pattern extraction
            search_pool = f"{title} {body_text}"
            
            # Locate contiguous string patterns matching base64 layout properties
            potential_blocks = re.findall(r'[A-Za-z0-9+/=]{16,}', search_pool)
            
            for base64_chunk in potential_blocks:
                decoded = loose_base64_decode(base64_chunk)
                if not decoded:
                    continue

                # Locate any paste text links embedded inside the decoded string footprint
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

    except Exception as parse_err:
        print(f"JSON parsing array compilation exception: {parse_err}")
        return

    # 3. Synchronize outputs back up to Cloudflare KV Namespace key
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
