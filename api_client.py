import requests
import time
from constants import CHECKS_URL, FREE_SLOTS_URL, MAX_RETRIES, BASE_BACKOFF_SECONDS
from auth import login, refresh_token
from utils import wait_seconds

class AlmavivaAPIClient:
    def __init__(self, email, password, proxy_manager=None, log_callback=None):
        self.email = email
        self.password = password
        self.proxy_manager = proxy_manager
        self.log_callback = log_callback
        self.token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.session = requests.Session()

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _get_proxy_dict(self):
        if self.proxy_manager and self.proxy_manager.enabled:
            proxy_url = self.proxy_manager.get_proxy_url_for_requests()
            if proxy_url:
                return {"http": proxy_url, "https": proxy_url}
        return None

    def login(self):
        self.log("🔑 Login via API in corso...")
        proxy_dict = self._get_proxy_dict()
        try:
            token_data = login(self.email, self.password, proxy_dict)
            self.token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token")
            self.token_expiry = token_data.get("expires_at", time.time() + 900)
            self.log("✅ Login API riuscito, token ottenuto.")
            return True
        except Exception as e:
            self.log(f"❌ Login API fallito: {e}")
            return False

    def _refresh_access_token(self):
        if not self.refresh_token:
            return self.login()
        self.log("🔄 Rinnovo token tramite refresh_token...")
        proxy_dict = self._get_proxy_dict()
        try:
            token_data = refresh_token(self.refresh_token, proxy_dict)
            self.token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", self.refresh_token)
            self.token_expiry = token_data.get("expires_at", time.time() + 900)
            self.log("✅ Token rinnovato con successo.")
            return True
        except Exception as e:
            self.log(f"❌ Rinnovo token fallito: {e}, eseguo login completo...")
            return self.login()

    def _ensure_token(self):
        if not self.token or time.time() >= self.token_expiry - 60:
            return self._refresh_access_token()
        return True

    def _request_with_backoff(self, method, url, **kwargs):
        for attempt in range(MAX_RETRIES):
            if not self._ensure_token():
                raise Exception("Token non valido")
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
                    self.token = None
                    continue
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