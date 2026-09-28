import os
import urllib.request
import urllib.parse
import json
import base64
import re
import html
import time

# Direct system agent signature safely handles public API gateway connections
USER_AGENT = "IPTV-Custom-Aggregator-Pipeline/9.0 (Linux; x64) GitHub-Cloud-Runner"

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID")
API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

cf_p1 = "https:" + "//" + "api."
cf_p2 = "cloudflare.com" + "/client" + "/v4" + "/accounts"
CF_MASTER_API_URL = cf_p1 + cf_p2

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
    print("Connecting directly to raw public API data stream...")
    # Direct native endpoint completely removes the need for unstable proxy web addresses
    target_feed = "https://reddit.com"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    
    status, raw_text_payload = make_api_request(target_feed, headers)
    if status != 200:
        print(f"Primary API gateway choked (HTTP {status}). Retrying via backup mirror...")
        fallback_feed = "https://workers.dev"
        status, raw_text_payload = make_api_request(fallback_feed, headers)
        if status != 200:
            print("Error: All primary and backup data streams are unreachable.")
            return

    discovered_urls = []
    kv_endpoint = f"{CF_MASTER_API_URL}/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values/raw_credentials"
    kv_headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "text/plain"}

    status, existing_kv_text = make_api_request(kv_endpoint, kv_headers)
    if status == 200:
        discovered_urls = [line.strip() for line in existing_kv_text.split("\n") if line.strip()]
        print(f"Loaded {len(discovered_urls)} active database lines from Cloudflare KV.")

    post_ids = []
    target_threads_data = {}
    current_time = time.time()
    one_day_seconds = 24 * 60 * 60

    try:
        json_payload = json.loads(raw_text_payload)
        # Parse data whether it's wrapped in standard format or flat arrays
        children = json_payload.get("data", {}).get("children", []) if isinstance(json_payload, dict) else json_payload
        
        if not isinstance(children, list):
            children = []

        for child in children:
            p_data = child.get("data", {}) if "data" in child else child
            pid = p_data.get("id")
            title = p_data.get("title", "")
            body_text = p_data.get("selftext", "")
            created_utc = p_data.get("created_utc", 0)
            
            # ⚠️ STRICT AGE FILTER: Skip if the post is older than 24 hours
            if current_time - created_utc > one_day_seconds:
                continue
                
            if pid:
                post_ids.append(pid)
                # Store the uncut body markdown directly to avoid separate post page fetches
                target_threads_data[pid] = f"{title} {body_text}"

        print(f"Dynamic analyzer successfully isolated {len(post_ids)} active thread targets from the last 24 hours.")

    except Exception as parse_err:
        print(f"Data stream text unpack exception: {parse_err}")
        return

    # Step 2: Iterate directly through the un-clipped body data of today's active threads
    for pid in post_ids:
        search_pool = target_threads_data.get(pid, "")
        print(f"Processing un-clipped Markdown body content for post ID: {pid}")
        
        # Scan strings for potential base64 layouts blocks
        potential_blocks = re.findall(r'[A-Za-z0-9+/=\s\n\r]{24,}', search_pool)
        
        for chunk_with_spaces in potential_blocks:
            decoded = loose_base64_decode(chunk_with_spaces)
            
            if decoded and ("paste" in decoded or "get.php" in decoded or "http" in decoded):
                paste_links = re.findall(r'https?://?:paste\.sh|pastebin\.com|controlc\.com|rentry\.co/[^\s\n\r"\'><]+', decoded)
                
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
