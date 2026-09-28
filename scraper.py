import os
import requests
import base64
import re
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Google RSS query pipeline translates search strings to live URL endpoints cleanly
# It targets the exact sub-community and pulls its newest indexed layers
g1 = "https:" + "//" + "news.google.com"
g2 = "/rss/search?q=" + "site:reddit.com/r/IPTV_ZONENEW"
g3 = "&" + "hl=en-US&gl=US&ceid=US:en"

GOOGLE_SEARCH_RSS = g1 + g2 + g3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Parser-Engine/7.0"

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

    # 1. Query Google Indexer to harvest the newest active post URLs
    print(f"Querying Google Search index layers: {GOOGLE_SEARCH_RSS}")
    try:
        g_response = session.get(GOOGLE_SEARCH_RSS, headers={"User-Agent": USER_AGENT}, timeout=15)
        if g_response.status_code != 200:
            print(f"Google indexing fetch failed: HTTP {g_response.status_code}")
            return
    except Exception as g_err:
        print(f"Failed to access search index network: {g_err}")
        return

    # Use regex to pluck out individual post links discovered by Google
    discovered_post_links = re.findall(r'<link[^>]*>(https?://old\.reddit\.com/r/IPTV_ZONENEW/[^\s\n\r"\'><]+)', g_response.text)
    
    # Fallback to check standard reddit link variations in the search feed
    if not discovered_post_links:
        standard_links = re.findall(r'<link[^>]*>(https?://(?:www\.)?reddit\.com/r/IPTV_ZONENEW/[^\s\n\r"\'><]+)', g_response.text)
        for s_l in standard_links:
            # Reconstruct them to old.reddit layout formats instantly to secure parsing
            old_version = s_l.replace("www.reddit.com", "old.reddit.com").replace("reddit.com", "old.reddit.com")
            discovered_post_links.append(old_version)

    # Deduplicate the target array list
    discovered_post_links = list(set(discovered_post_links))
    print(f"Google successfully returned {len(discovered_post_links)} fresh active community targets.")

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

    # 2. Iterate through each real link returned by Google's live index search map
    for target_post_url in discovered_post_links:
        print(f"Navigating directly into live thread: {target_post_url}")
        try:
            # Fetch the actual post body text directly
            post_response = session.get(target_post_url, headers={"User-Agent": USER_AGENT}, timeout=12)
            if post_response.status_code != 200:
                continue
            
            # Target the content pools inside the post's description layers
            potential_blocks = re.findall(r'[A-Za-z0-9+/=]{16,}', post_response.text)
            
            for base64_chunk in potential_blocks:
                decoded = loose_base64_decode(base64_chunk)
                if not decoded:
                    continue

                # Isolate paste links inside the decoded string footprint
                paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                for paste_url in paste_links:
                    raw_url = paste_url.strip()
                    if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                    if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                        raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                    print(f"-> Uncovered paste vectors: {raw_url}")
                    try:
                        paste_res = session.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=10)
                        if paste_res.status_code == 200:
                            parsed_links = extract_credentials_from_bulk(paste_res.text)
                            for target_link in parsed_links:
                                if target_link not in discovered_urls:
                                    discovered_urls.append(target_link)
                                    print(f"   [Harvested Link Added]: {target_link}")
                    except Exception:
                        pass

                direct_links = extract_credentials_from_bulk(decoded)
                for d_link in direct_links:
                    if d_link not in discovered_urls:
                        discovered_urls.append(d_link)
                        print(f"   [Direct Link Added]: {d_link}")

        except Exception as thread_err:
            print(f"Thread skipping checkpoint: {thread_err}")

    # 3. Synchronize aggregated outputs back to your profile namespace
    if len(discovered_urls) > 0:
        compiled_dump = "\n".join(discovered_urls)
        try:
            kv_response = session.put(kv_endpoint, headers=kv_headers, data=compiled_dump, timeout=15)
            if kv_response.status_code == 200:
                print(f"Success! Sync completed. Current total pool size: {len(discovered_urls)} lines.")
            else:
                print(f"Failed sync package delivery: {kv_response.text}")
        except Exception as put_err:
            print(f"Network write error: {put_err}")
    else:
        print("No unique credentials isolated during this tracking phase.")

if __name__ == "__main__":
    main()
