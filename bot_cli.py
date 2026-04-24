#!/usr/bin/env python3
"""
Almaviva Bot - CLI Interface
Monitoraggio appuntamenti da riga di comando con login diretto API.
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta
from constants import AUTH_TOKEN_URL, CLIENT_ID, CHECKS_URL, FREE_SLOTS_URL

# ==================== CONFIGURAZIONE ====================
# MODIFICA QUESTI VALORI CON LE TUE CREDENZIALI
EMAIL = "tua_email@example.com"
PASSWORD = "tua_password"
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
        if r.status_code == 400:
            try:
                error_data = r.json()
                if "check-can-create" in str(error_data):
                    return "account_limit"
            except:
                pass
            return False
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

def save_token(token_data):
    with open("token_cache.json", "w") as f:
        json.dump(token_data, f)
    print("Token salvato in cache")

def load_cached_token():
    if os.path.exists("token_cache.json"):
        with open("token_cache.json", "r") as f:
            data = json.load(f)
        if data.get("expires_at", 0) > time.time() + 60:
            print("Token valido trovato in cache")
            return data
    return None

def main():
    # Prova a caricare token da cache
    cached = load_cached_token()
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
    
    print(f"Inizio monitoraggio ogni {CHECK_INTERVAL_SEC} secondi...")
    target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"Data di riferimento: {target_date}")
    
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
                    save_token(new_data)
                    print("Token rinnovato con successo")
                    continue
            token = get_token()
            if not token:
                print("Rinnovo fallito, riprovo tra 60 secondi.")
                time.sleep(60)
            continue
        
        if result == "rate_limit":
            print("Rate limit (429), attendo 60 secondi...")
            time.sleep(60)
            continue
        
        if result == "account_limit":
            print("Limite account raggiunto, attendo 30 minuti...")
            time.sleep(30 * 60)
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
                print(f"🎯 Slot trovati: {slots}")
                break
            else:
                print(f"Nessuno slot per la data {target_date}, continuo...")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nessun appuntamento.")
        
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()