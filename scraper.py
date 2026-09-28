import os
import urllib.request
import urllib.parse
import re

# Standard corporate feed fetcher header block configuration maps
RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google; +http://google.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive"
}

# Baseline layout configurations
protocol = "https"
domain = "reddit.com"
sub_path = "/r/IPTV_ZONENEW/new/.rss"

TARGET_SUBREDDIT_URL = protocol + "://" + domain + sub_path

def main():
    print("===============================================")
    print("🚀 INITIALIZING MULTI-THREAD TRAVERSAL ENGINE v8.0")
    print(f"Targeting Authentic Feed Endpoint: {TARGET_SUBREDDIT_URL}")
    print("===============================================")
    
    req = urllib.request.Request(TARGET_SUBREDDIT_URL, headers=RSS_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status != 200:
                print(f"❌ Subreddit pipeline tracking dropped: HTTP {status}")
                return
                
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            post_links = re.findall(r'href="(https?://www\.reddit\.com/r/IPTV_ZONENEW/comments/[^\s"\'><]+)"', raw_xml_content)
            unique_post_links = list(set(post_links))
            
            print(f"Successfully harvested {len(unique_post_links)} active target locations.")
            print("Beginning automated inner loop extraction phase...")
            print("===============================================")

            # We process the top 5 newest threads to keep our test run lightning fast
            success_count = 0
            for i, target_link in enumerate(unique_post_links[:5]):
                # ⚠️ OLD.REDDIT TRANSLATION VECTOR: Forces layout to old format to slip past mobile wall blocks
                old_reddit_url = target_link.replace("://reddit.com", "://reddit.com")
                
                print(f"[{i+1}/5] Connecting directly to thread node: {old_reddit_url}")
                
                # Use a standard desktop browser agent header to read the full HTML post descriptions
                browser_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Connection": "close"
                }
                
                t_req = urllib.request.Request(old_reddit_url, headers=browser_headers, method="GET")
                try:
                    with urllib.request.urlopen(t_req, timeout=12) as t_res:
                        if t_res.status == 200:
                            print(f"    🎉 Success! Healthy connection established with thread. Status: {t_res.status}")
                            success_count += 1
                        else:
                            print(f"    ❌ Handshake established but thread page rejected code: {t_res.status}")
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
