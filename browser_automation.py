import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from constants import LOGIN_URL

class BrowserAutomation:
    def __init__(self, account, headless=False, log_callback=None):
        self.account = account
        self.headless = headless
        self.log_callback = log_callback
        self.driver = None
        self.token = None

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _init_driver(self):
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--incognito")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return uc.Chrome(options=options)

    def login(self):
        self.log("🌐 Avvio browser per login...")
        if self.driver is None:
            self.driver = self._init_driver()
        self.driver.get(LOGIN_URL)
        time.sleep(3)

        current_url = self.driver.current_url
        if "egyiam.almaviva-visa.it" not in current_url and "login" not in current_url.lower():
            try:
                prenota = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "Prenota")]'))
                )
                prenota.click()
                self.log("Cliccato su Prenota")
                WebDriverWait(self.driver, 10).until(EC.url_contains("egyiam.almaviva-visa.it"))
            except Exception as e:
                self.log(f"Pulsante Prenota non trovato: {e}")

        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.ID, "kc-form-login")))
            self.driver.find_element(By.ID, "username").send_keys(self.account["email"])
            self.driver.find_element(By.ID, "password").send_keys(self.account["password"])
            self.driver.find_element(By.ID, "kc-login").click()
            self.log("Credenziali inviate")
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "Prenota")]')))
            self.log("✅ Login completato")
        except Exception as e:
            self.log(f"❌ Login fallito: {e}")
            return False

        try:
            prenota = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "Prenota")]'))
            )
            prenota.click()
            self.log("Cliccato su Prenota dopo login")
            time.sleep(3)
        except:
            pass

        try:
            token = self.driver.execute_script("""
                return localStorage.getItem('access_token') || 
                       localStorage.getItem('token') || 
                       sessionStorage.getItem('access_token') || 
                       sessionStorage.getItem('token');
            """)
            if token:
                self.token = token
                self.log("✅ Token estratto dallo storage")
                return True
            else:
                self.log("❌ Token non trovato")
                return False
        except Exception as e:
            self.log(f"Errore estrazione token: {e}")
            return False

    def refresh_token(self):
        self.log("🔄 Rinnovo token...")
        try:
            self.driver.get("https://egy.almaviva-visa.it/appointment")
            time.sleep(5)
            if self._extract_token():
                self.log("✅ Token rinnovato")
                return True
            else:
                self.driver.refresh()
                time.sleep(5)
                return self._extract_token()
        except Exception as e:
            self.log(f"Errore rinnovo token: {e}")
            return False

    def quit(self):
        if self.driver:
            self.driver.quit()