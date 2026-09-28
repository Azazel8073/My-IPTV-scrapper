import os
import requests
import base64
import re
import html
import subprocess
import json
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

USER_AGENT = "IPTV-Custom-Aggregator-Pipeline/5.0 (Linux; x64) GitHub-Runner-Instance"

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

    # Step 1: Direct JSON retrieval utilizing curl sub-processes to bypass rate throttles
    print("Executing native data pipeline request directly to Reddit API layer...")
    target_json_url = "https://reddit.com"
    
    raw_json_data = ""
    try:
        # Command line curl completely avoids python connection fingerprint blocks
        cmd = ["curl", "-s", "-A", USER_AGENT, target_json_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode == 0 and "data" in result.stdout:
            raw_json_data = result.stdout
            print("Success! Downloaded authentic un-cached JSON text map.")
    except Exception as cmd_err:
        print(f"Shell pipeline command execution failed: {cmd_err}")
        return

    if not raw_json_data:
        print("Error: Direct connection endpoint throttled or returned empty payload.")
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

    # Step 2: Parse out json dictionary arrays to find the hidden base64 string dumps
    try:
        payload = json.loads(raw_json_data)
        posts = payload.get("data", {}).get("children", [])
        print(f"Scanning the latest {len(posts)} raw community posts descriptions...")

        for post in posts:
            post_data = post.get("data", {})
            title = post_data.get("title", "")
            body_text = post_data.get("selftext", "")
            
            # Extract content from both the title and text body components
            search_pool = f"{title} {body_text}"
            
            # Locate contiguous character chunks matching base64 properties length rules globally
            potential_blocks = re.findall(r'[A-Za-z0-9+/=\s\n\r]{24,}', search_pool)
            
            for chunk_with_spaces in potential_blocks:
                decoded = loose_base64_decode(chunk_with_spaces)
                
                # Check if the decoded block contains any of our target links or domains
                if decoded and ("paste" in decoded or "get.php" in decoded or "http" in decoded):
                    paste_links = re.findall(r'https?://(?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co)/[^\s\n\r"\'><]+', decoded)
                    
                    for paste_url in paste_links:
                        raw_url = paste_url.strip()
                        if "paste.sh/" in raw_url and "/raw/" not in raw_url:
                            raw_url = raw_url.replace("paste.sh/", "paste.sh/raw/")
                        if "://pastebin.com" in raw_url and "/raw/" not in raw_url:
                            raw_url = raw_url.replace("://pastebin.com", "://pastebin.comraw/")

                        print(f"   -> Found hidden paste payload: {raw_url}")
                        try:
                            paste_res = session.get(raw_url, headers={"User-Agent": USER_AGENT}, timeout=12)
                            if paste_res.status_code == 200:
                                parsed_links = extract_credentials_from_bulk(paste_res.text)
                                for target_link in parsed_links:
                                    if target_link not in discovered_urls:
                                        discovered_urls.append(target_link)
                                        print(f"      [Successfully Appended]: {target_link}")
                        except Exception as p_err:
                            print(f"      Failed loading contents: {p_err}")

                    direct_links = extract_credentials_from_bulk(decoded)
                    for d_link in direct_links:
                        if d_link not in discovered_urls:
                            discovered_urls.append(d_link)
                            print(f"      [Successfully Appended Direct]: {d_link}")

    except Exception as parse_err:
        print(f"Data stream text unpack exception: {parse_err}")
        return

    # Step 3: Synchronize updates back up to Cloudflare KV Namespace key
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
