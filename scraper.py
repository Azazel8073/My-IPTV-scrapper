import os
import urllib.request
import urllib.parse
import re

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google; +http://google.com)",
    "Accept": "application/xml,text/xml,*/*",
    "Connection": "keep-alive"
}

# The pristine, manually verified layout string paths
protocol = "https"
domain = "reddit.com"
sub_path = "/r/IPTV_ZONENEW/new/.rss"

TARGET_SUBREDDIT_URL = protocol + "://" + domain + sub_path

def main():
    print("===============================================")
    print("🚀 BOB INITIALIZING POST PATH EXTRACTION v7.0")
    print(f"Targeting Authentic Feed: {TARGET_SUBREDDIT_URL}")
    print("===============================================")
    
    req = urllib.request.Request(TARGET_SUBREDDIT_URL, headers=RSS_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status != 200:
                print(f"❌ Subreddit feed tracking dropped: HTTP {status}")
                return
                
            # Download the complete, uncut text layout stream from the feed
            raw_xml_content = response.read().decode('utf-8', errors='ignore')
            
            # 🔍 THE PATH EXTRACTOR: Look for standard XML link reference structures pointing to comments
            post_links = re.findall(r'href="(https?://www\.reddit\.com/r/IPTV_ZONENEW/comments/[^\s"\'><]+)"', raw_xml_content)
            
            # Deduplicate the gathered array list
            unique_post_links = list(set(post_links))
            
            print("===============================================")
            print(f"🎉 SUCCESS! BOB HAS EXTRACTED ACTIVE THREAD LINKS!")
            print(f"Total Unique Posts Isolated: {len(unique_post_links)}")
            print("===============================================")
            
            # Print out the first 3 links found so we can see the exact target links
            for i, link in enumerate(unique_post_links[:3]):
                print(f"Isolated Post Vector [{i+1}]: {link}")
            return

    except Exception as network_error:
        print(f"❌ Extraction engine failed at the gate! Error text: {network_error}")
        return

if __name__ == "__main__":
    main()
