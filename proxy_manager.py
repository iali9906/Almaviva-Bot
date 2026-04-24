import random
import requests

class ProxyManager:
    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.get("proxy_enabled", False)
        self.proxy_list = settings.get("proxy_list", [])
        self.current_index = 0

    def is_configured(self):
        return self.enabled and self.proxy_list

    def get_next_proxy(self):
        if not self.is_configured():
            return None
        proxy = self.proxy_list[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_list)
        return proxy

    def get_proxy_url_for_requests(self, proxy=None):
        if not self.enabled:
            return None
        if proxy is None:
            proxy = self.get_next_proxy()
        if not proxy:
            return None
        parts = proxy.split(':')
        if len(parts) >= 2:
            host = parts[0]
            port = parts[1]
            username = parts[2] if len(parts) > 2 else ""
            password = parts[3] if len(parts) > 3 else ""
            if username and password:
                return f"http://{username}:{password}@{host}:{port}"
            else:
                return f"http://{host}:{port}"
        return None

    def test_proxy(self, log_callback=None):
        if not self.is_configured():
            return False, "Nessun proxy configurato"
        proxy_url = self.get_proxy_url_for_requests(self.proxy_list[0])
        try:
            proxies = {"http": proxy_url, "https": proxy_url}
            resp = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
            if resp.status_code == 200:
                return True, resp.json().get("origin")
            else:
                return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)