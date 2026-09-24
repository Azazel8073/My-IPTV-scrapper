import os
import requests
import base64
import re
import xml.etree.ElementTree as ET

# Safe chunk segments to bypass phone copy-paste limitations
URL_PART1 = "https://reddit.com"
URL_PART2 = "IPTV_ZONENEW/new/.rss?"
URL_PART3 = "cache-bust=1790165525008&screen_view_count=1&ext-referrer=DIRECT"

SUBREDDIT_RSS_URL = URL_PART1 + URL_PART2 + URL_PART3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Parser-Engine/3.0"

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
        if "username=" in link and "password=" in link:
            if link not in found:
                found.append(link)
    return found

def main():
    print(f"Connecting to target endpoint: {SUBREDDIT_RSS_URL}")
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(SUBREDDIT_RSS_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"Reddit RSS connection failed: HTTP {response.status_code}")
        return

    discovered_urls = []

    # 1. Fetch current pool state from Cloudflare KV
    kv_endpoint = f"https://cloudflare.com{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/plain"
    }

    try:
        existing_kv = requests.get(kv_endpoint, headers=kv_headers)
        if existing_kv.status_code == 200:
            discovered_urls = [line.strip() for line in existing_kv.text.split("\n") if line.strip()]
            print(f"Loaded {len(discovered_urls)} existing active lines from Cloudflare KV.")
    except Exception as e:
        print(f"KV data loading skipped: {e}")

    # 2. Parse out XML entries from the RSS stream data
    try:
        root = ET.fromstring(response.content)
        namespaces = {'atom': 'http://w3.org'}
        entries = root.findall('atom:entry', namespaces)
        print(f"Scanning the latest {len(entries)} community post layers...")

        for entry in entries:
            title = entry.find('atom:title', namespaces).text or ""
            content_element = entry.find('atom:content', namespaces)
            content_html = content_element.text or "" if content_element is not None else ""
            
            search_pool = f"{title} {content_html}"
            potential_blocks = re.findall(r'[A-Za-z0-9+/=]{16,}', search_pool)
            
            for block in potential_blocks:
                decoded = loose_base64_decode(block)
                
                if decoded:
                    # Check text block for any hidden paste URLs
                    paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                    
                    for paste_url in paste_links:
                        raw_url = paste_url.strip()
                        if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                            raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                        if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                            raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                        print(f"Found hidden paste URL link vector: {raw_url}")
                        try:
                            paste_res = requests.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=10)
                            if paste_res.status_code == 200:
                                parsed_links = extract_credentials_from_bulk(paste_res.text)
                                for target_link in parsed_links:
                                    if target_link not in discovered_urls:
                                        discovered_urls.append(target_link)
                                        print(f"-> Appended: {target_link}")
                        except Exception as n_err:
                            print(f"Failed loading contents from paste server: {n_err}")

                    direct_links = extract_credentials_from_bulk(decoded)
                    for d_link in direct_links:
                        if d_link not in discovered_urls:
                            discovered_urls.append(d_link)
                            print(f"-> Appended (Direct): {d_link}")

    except Exception as xml_err:
        print(f"XML execution parsing runtime error: {xml_err}")
        return

    # 3. Synchronize updates back up to Cloudflare KV
    if len(discovered_urls) > 0:
        compiled_dump = "\n".join(discovered_urls)
        kv_response = requests.put(kv_endpoint, headers=kv_headers, data=compiled_dump)
        if kv_response.status_code == 200:
            print(f"Success! Sync completed. Current pool size: {len(discovered_urls)} lines.")
        else:
            print(f"Failed sync package delivery: {kv_response.text}")
    else:
        print("No new unique credentials found during this cycle check.")

if __name__ == "__main__":
    main()

