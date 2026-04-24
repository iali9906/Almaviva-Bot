#!/usr/bin/env python3
"""
Almaviva Bot - CLI Interface
Monitoraggio appuntamenti da riga di comando.
Legge le credenziali dal file almaviva_config.json
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta
from constants import AUTH_TOKEN_URL, CLIENT_ID, CHECKS_URL, FREE_SLOTS_URL

# ==================== CARICA CONFIGURAZIONE ====================
CONFIG_FILE = "almaviva_config.json"

def load_first_account():
    """Carica il primo account dal file di configurazione JSON"""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Errore: File {CONFIG_FILE} non trovato")
        return None, None
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        
        if not config.get("accounts") or len(config["accounts"]) == 0:
            print("❌ Errore: Nessun account trovato nel file di configurazione")
            return None, None
        
        account = config["accounts"][0]
        email = account.get("email")
        password = account.get("password")
        
        if not email or not password:
            print("❌ Errore: Email o password mancanti per il primo account")
            return None, None
        
        print(f"✅ Caricato account: {email}")
        return email, password
    
    except json.JSONDecodeError:
        print(f"❌ Errore: File {CONFIG_FILE} non è un JSON valido")
        return None, None
    except Exception as e:
        print(f"❌ Errore durante il caricamento della configurazione: {e}")
        return None, None

# Carica le credenziali dal file
EMAIL, PASSWORD = load_first_account()
if not EMAIL or not PASSWORD:
    print("Impossibile proseguire. Verifica che almaviva_config.json esista e contenga un account valido.")
    exit(1)

# ==================== CONFIGURAZIONE ====================
VISA_ID = 8
OFFICE_ID = 1
SERVICE_LEVEL = 1
CHECK_INTERVAL_SEC = 30

# ==================== FUNZIONI ====================
def get_token():
    """Ottiene il token OAuth2 con grant_type=password"""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": EMAIL,
        "password": PASSWORD
    }
    try:
        r = requests.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
        if r.status_code != 200:
            print(f"[{datetime.now()}] Login fallito: {r.status_code}")
            return None
        token_data = r.json()
        print(f"[{datetime.now()}] Login OK, token ottenuto.")
        return token_data["access_token"]
    except Exception as e:
        print(f"[{datetime.now()}] Errore login: {e}")
        return None

def refresh_token(refresh_token_value):
    """Rinnova il token usando il refresh_token"""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token_value
    }
    try:
        r = requests.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

def check_availability(token):
    url = f"{CHECKS_URL}?officeId={OFFICE_ID}&visaId={VISA_ID}&serviceLevelId={SERVICE_LEVEL}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 401:
            return "expired"
        if r.status_code == 429:
            return "rate_limit"
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Errore check: {e}")
        return False

def get_free_slots(token, date):
    url = f"{FREE_SLOTS_URL}?officeId={OFFICE_ID}&quantity=1&date={date}&type=WEB"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 401:
            return "expired"
        if r.status_code == 429:
            return "rate_limit"
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Errore slots: {e}")
        return []

def save_token_cache(token_data):
    """Salva il token in cache per future sessioni"""
    cache_file = "token_cache.json"
    with open(cache_file, "w") as f:
        json.dump(token_data, f)
    print(f"Token salvato in cache ({cache_file})")

def load_token_cache():
    """Carica il token dalla cache se ancora valido"""
    cache_file = "token_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time() + 60:
                print(f"Token valido trovato in cache (scade alle {datetime.fromtimestamp(data['expires_at']).strftime('%H:%M:%S')})")
                return data
        except:
            pass
    return None

def main():
    # Prova a caricare token da cache
    cached = load_token_cache()
    if cached:
        token = cached["access_token"]
        refresh = cached.get("refresh_token")
        print(f"Token valido fino a {datetime.fromtimestamp(cached['expires_at'])}")
    else:
        token = get_token()
        refresh = None
        if not token:
            print("Impossibile proseguire. Verifica le credenziali.")
            return
    
    print(f"💰 Account: {EMAIL}")
    print(f"🎯 Visto ID: {VISA_ID}")
    print(f"🏢 Ufficio: {OFFICE_ID}")
    print(f"🔄 Intervallo: {CHECK_INTERVAL_SEC} secondi")
    print(f"🚀 Inizio monitoraggio... (Ctrl+C per fermare)")
    
    target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"📅 Data di riferimento: {target_date}")
    
    while True:
        result = check_availability(token)
        
        if result == "expired":
            print("Token scaduto, rinnovo...")
            if refresh:
                new_data = refresh_token(refresh)
                if new_data:
                    token = new_data["access_token"]
                    refresh = new_data.get("refresh_token")
                    new_data["expires_at"] = time.time() + new_data.get("expires_in", 900)
                    save_token_cache(new_data)
                    print("Token rinnovato con successo")
                    continue
            token = get_token()
            if not token:
                print("Rinnovo fallito, riprovo tra 60 secondi.")
                time.sleep(60)
            continue
        
        if result == "rate_limit":
            print("⚠️ Rate limit (429), attendo 60 secondi...")
            time.sleep(60)
            continue
        
        if result is True:
            print("✅ Disponibilità rilevata! Recupero slot...")
            slots = get_free_slots(token, target_date)
            if slots == "expired":
                continue
            if slots == "rate_limit":
                time.sleep(60)
                continue
            if slots and len(slots) > 0:
                print(f"🎯 Slot trovati per {target_date}: {slots}")
                print("🏆 Appuntamento disponibile! Vai su https://egy.almaviva-visa.it")
                break
            else:
                print(f"Nessuno slot per la data {target_date}, continuo...")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nessun appuntamento.")
        
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Monitoraggio fermato dall'utente")