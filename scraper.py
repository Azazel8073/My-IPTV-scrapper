import os
import requests
import base64
import re
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Building paths using short segments to bypass mobile screen issues
url_a = "https:" + "//" + "old."
url_b = "reddit.com" + "/r" + "/"
url_c = "IPTV" + "_ZONE" + "NEW" + "/"
url_d = "new" + "/" + ".rss" + "?"
url_e = "cache" + "-bust" + "=1790165525008"
url_f = "&" + "screen" + "_view" + "_count" + "=1"
url_g = "&" + "ext" + "-referrer" + "=DIRECT"

SUBREDDIT_RSS_URL = url_a + url_b + url_c + url_d + url_e + url_f + url_g
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Parser-Engine/6.0"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

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
    # Setup a robust session container with automatic retry logic for network blinks
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # Automatically retry 5 times
        backoff_factor=2,  # Wait longer between each retry (2s, 4s, 8s...)
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    print(f"Connecting to target RSS layout endpoint: {SUBREDDIT_RSS_URL}")
    try:
        response = session.get(SUBREDDIT_RSS_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
        if response.status_code != 200:
            print(f"Reddit connection failed: HTTP {response.status_code}")
            return
    except Exception as reddit_err:
        print(f"Failed to access Reddit servers: {reddit_err}")
        return

    discovered_urls = []

    # Clean Cloudflare storage endpoint framework
    kv_endpoint = f"https://cloudflare.com{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/plain"
    }

    try:
        existing_kv = session.get(kv_endpoint, headers=kv_headers, timeout=15)
        if existing_kv.status_code == 200:
            discovered_urls = [line.strip() for line in existing_kv.text.split("\n") if line.strip()]
            print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")
    except Exception as e:
        print(f"KV initial loading skipped: {e}")

    raw_html_content = response.text
    entry_blocks = re.findall(r'<entry>.*?</entry>', raw_html_content, re.DOTALL)
    print(f"Scanning the latest {len(entry_blocks)} raw text community layers...")

    for block in entry_blocks:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
        content_match = re.search(r'<content[^>]*>(.*?)</content>', block, re.DOTALL)
        
        title_text = title_match.group(1) if title_match else ""
        content_text = content_match.group(1) if content_match else ""
        
        search_pool = f"{title_text} {content_text}"
        potential_blocks = re.findall(r'[A-Za-z0-9+/=]{16,}', search_pool)
        
        for base64_chunk in potential_blocks:
            decoded = loose_base64_decode(base64_chunk)
            if not decoded:
                continue

            paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
            for paste_url in paste_links:
                raw_url = paste_url.strip()
                if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                    raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                print(f"Found hidden paste link address: {raw_url}")
                try:
                    paste_res = session.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=10)
                    if paste_res.status_code == 200:
                        parsed_links = extract_credentials_from_bulk(paste_res.text)
                        for target_link in parsed_links:
                            if target_link not in discovered_urls:
                                discovered_urls.append(target_link)
                                print(f"-> Appended: {target_link}")
                except Exception as n_err:
                    print(f"Failed loading contents from paste destination: {n_err}")

            direct_links = extract_credentials_from_bulk(decoded)
            for d_link in direct_links:
                if d_link not in discovered_urls:
                    discovered_urls.append(d_link)
                    print(f"-> Appended (Direct Link): {d_link}")

    if len(discovered_urls) > 0:
        compiled_dump = "\n".join(discovered_urls)
        try:
            kv_response = session.put(kv_endpoint, headers=kv_headers, data=compiled_dump, timeout=15)
            if kv_response.status_code == 200:
                print(f"Success! Sync completed. Current pool size: {len(discovered_urls)} lines.")
            else:
                print(f"Failed sync package delivery: {kv_response.text}")
        except Exception as put_err:
            print(f"Network error trying to write data back to Cloudflare: {put_err}")
    else:
        print("No unique credentials isolated during this tracking phase.")

if __name__ == "__main__":
    main()
