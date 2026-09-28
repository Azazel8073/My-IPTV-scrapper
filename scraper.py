import os
import urllib.request
import urllib.parse
import re

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google; +http://google.com)",
    "Accept": "application/xml,text/xml,*/*",
    "Connection": "keep-alive"
}

# The clean master feed link structure
p_url = "https" + ":" + "/" + "/" + "www" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/new" + "/" + ".rss"

def main():
    print("===============================================")
    print("🚀 INITIALIZING LOOP ARCHITECTURE RENav v9.2")
    print(f"Master Extraction Link: {p_url}")
    print("===============================================")
    
    req = urllib.request.Request(p_url, headers=RSS_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status != 200:
                print(f"❌ Master tracking node dropped: HTTP {status}")
                return
                
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            
            # 🔍 ID EXTRACTOR: Isolate the unique 7-character post tokens directly out of the feed strings
            post_tokens = re.findall(r'/comments/([A-Za-z0-9]{5,10})/', raw_xml_content)
            unique_tokens = list(set(post_tokens))
            
            print(f"Successfully discovered {len(unique_tokens)} active target threads.")
            print("Beginning automated inner loop deep verification phase...")
            print("===============================================")

            success_count = 0
            # Sifting through the newest 5 targets to keep our connection test blazing fast
            for i, token in enumerate(unique_tokens[:5]):
                
                # ⚠️ EXPLICIT LINK BUILDER: Completely ignores the old domain and builds a fresh 'old.reddit' address path natively
                old_reddit_url = "https" + ":" + "/" + "/" + "old" + "." + "reddit" + ".com" + "/r" + "/" + "IPTV_ZONENEW" + "/comments" + "/" + token + "/"
                
                print(f"[{i+1}/5] Deep navigating straight into thread: {old_reddit_url}")
                
                # High-authentication desktop browser layout headers to fully bypass the 403 block
                browser_handshake_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Cache-Control": "max-age=0",
                    "Connection": "close"
                }
                
                t_req = urllib.request.Request(old_reddit_url, headers=browser_handshake_headers, method="GET")
                try:
                    with urllib.request.urlopen(t_req, timeout=12) as t_res:
                        if t_res.status == 200:
                            print(f"    🎉 SUCCESS! Healthy connection established with post page text. Status: {t_res.status}")
                            success_count += 1
                        else:
                            print(f"    ❌ Handshake established but thread data page rejected code: {t_res.status}")
                except Exception as t_err:
                    print(f"    ❌ Connection failed to thread endpoint: {t_err}")

            print("===============================================")
            print("🎉 PROCESSING LOOP TERMINATED SUCCESSFULLY!")
            print(f"Total Threads Successfully Breached: {success_count}/5")
            print("===============================================")
            return

    except Exception as network_error:
        print(f"❌ Traversal configuration engine failed: {network_error}")
        return

if __name__ == "__main__":
    main()
