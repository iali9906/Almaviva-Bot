import requests
from constants import CHECKS_URL, FREE_SLOTS_URL, MAX_RETRIES, BASE_BACKOFF_SECONDS
from utils import wait_seconds

class AlmavivaAPIClient:
    def __init__(self, token, proxy_manager=None, log_callback=None):
        self.token = token
        self.proxy_manager = proxy_manager
        self.log_callback = log_callback
        self.session = requests.Session()

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _update_proxy(self):
        if self.proxy_manager and self.proxy_manager.enabled:
            proxy_url = self.proxy_manager.get_proxy_url_for_requests()
            if proxy_url:
                self.session.proxies = {"http": proxy_url, "https": proxy_url}
                return True
        return False

    def _request_with_backoff(self, method, url, **kwargs):
        for attempt in range(MAX_RETRIES):
            self._update_proxy()
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {self.token}"
            try:
                resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
                if resp.status_code == 429:
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        wait_seconds(int(retry_after))
                    else:
                        wait_seconds(BASE_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                if resp.status_code == 401:
                    raise Exception("Token scaduto")
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait_seconds(BASE_BACKOFF_SECONDS * (2 ** attempt))
                continue
            except Exception as e:
                raise e
        raise Exception("Max retries exceeded")

    def check_availability(self, office_id, visa_id, service_level_id=1):
        url = f"{CHECKS_URL}?officeId={office_id}&visaId={visa_id}&serviceLevelId={service_level_id}"
        resp = self._request_with_backoff('GET', url)
        return resp.json()

    def get_free_slots(self, office_id, date, quantity=1):
        url = f"{FREE_SLOTS_URL}?officeId={office_id}&quantity={quantity}&date={date}&type=WEB"
        resp = self._request_with_backoff('GET', url)
        return resp.json()