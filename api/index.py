import os
import urllib.request
import urllib.parse
import re
import json
from http.server import BaseHTTPRequestHandler

# --- PIPELINE SYNC CONFIGURATIONS ---
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("CF_ACCOUNT_ID")
CF_NAMESPACE_ID = os.environ.get("CLOUDFLARE_NAMESPACE_ID") or os.environ.get("CF_NAMESPACE_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")

class handler(BaseHTTPRequestHandler):
    def get_top_working_link(self):
        """Pulls the freshest live link straight out of your existing Cloudflare KV storage."""
        if not all([CF_ACCOUNT_ID, CF_NAMESPACE_ID, CF_API_TOKEN]):
            return None
        url = f"https://cloudflare.com{CF_ACCOUNT_ID}/kv/namespaces/{CF_NAMESPACE_ID}/values/raw_credentials"
        
        # ✅ FIXED: Enforcing direct authenticated header request layer for Cloudflare integration
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CF_API_TOKEN}"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                if res.status == 200:
                    lines = res.read().decode('utf-8').splitlines()
                    for line in lines:
                        if line.strip().startswith("http"):
                            return line.strip()
        except Exception:
            pass
        return None

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.lower()
        
        # 1. THE ILLUSION: INTERCEPT M3U AND GET.PHP CALLS NATIVELY WITHOUT BLOCKING PORTS
        if "get" in path or path.endswith(".m3u") or "player_api.php" in path:
            working_link = self.get_top_working_link()
            if not working_link:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"#EXTM3U\n#EXTINF:-1,No Active Database Links Found")
                return

            try:
                target_parsed = urllib.parse.urlparse(working_link)
                incoming_params = urllib.parse.parse_qs(parsed_url.query)
                target_params = urllib.parse.parse_qs(target_parsed.query)
                
                # Merge query inputs safely
                for k, v in incoming_params.items():
                    if k not in ["username", "password"]:
                        target_params[k] = v

                flattened_params = {k: v[0] for k, v in target_params.items()}
                encoded_query = urllib.parse.urlencode(flattened_params)
                
                target_endpoint = f"http://{target_parsed.netloc}{target_parsed.pathname}?{encoded_query}"
                
                # ✅ FIXED: Utilizing clean browser profile builders to bypass server agent blocks
                opener = urllib.request.build_opener()
                opener.addheaders = [
                    ("User-Agent", "IPTVSmartersPro"),
                    ("Accept", "text/html,text/plain,application/json,*/*")
                ]
                
                with opener.open(target_endpoint, timeout=15) as res:
                    raw_data = res.read()
                    
                    # REWRITE ENGINE: Mask stream destinations to match your fresh Vercel URL layout
                    try:
                        text_payload = raw_data.decode('utf-8', errors='ignore')
                        host_header = self.headers.get('Host', 'localhost')
                        text_payload = re.sub(
                            r'(https?:\/\/|http:\/\/)[^\/]+\/(live|movie|series)\/([^\/]+)\/([^\/]+)\/([^\s\n\r]+)',
                            f"http://{host_header}/\\2/dummy/dummy/\\5",
                            text_payload
                        )
                        raw_data = text_payload.encode('utf-8')
                    except Exception:
                        pass

                    self.send_response(200)
                    self.send_header('Content-Type', res.headers.get('Content-Type', 'text/plain'))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(raw_data)
                    return
            except Exception as e:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"#EXTM3U\n#EXTINF:-1,Vercel Handler Proxy Loop Error: {str(e)}".encode('utf-8'))
                return

        # 2. VIDEO STREAM ROUTING (DIRECT RESILIENT 302 REDIRECTS)
        if "/live/" in path or "/movie/" in path or "/series/" in path:
            working_link = self.get_top_working_link()
            if working_link:
                target_parsed = urllib.parse.urlparse(working_link)
                target_params = urllib.parse.parse_qs(target_parsed.query)
                user = target_params.get("username", ["dummy"])[0]
                pw = target_params.get("password", ["dummy"])[0]
                
                segments = path.split("/")
                file_target = segments[-1]
                stream_type = "live"
                if "/movie/" in path: stream_type = "movie"
                if "/series/" in path: stream_type = "series"

                direct_stream_url = f"http://{target_parsed.netloc}/{stream_type}/{user}/{pw}/{file_target}"
                self.send_response(302)
                self.send_header('Location', direct_stream_url)
                self.end_headers()
                return

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Vercel Hybrid IPTV Proxy Active")
