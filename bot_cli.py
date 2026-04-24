#!/usr/bin/env python3
"""
Almaviva Bot - CLI Interface
Monitoraggio appuntamenti da riga di comando.
LEGGE TUTTI I DATI dal file almaviva_config.json
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta
from constants import AUTH_TOKEN_URL, CLIENT_ID, CHECKS_URL, FREE_SLOTS_URL

# ==================== CARICA CONFIGURAZIONE COMPLETA ====================
CONFIG_FILE = "almaviva_config.json"

def load_config_from_file():
    """Carica l'intero file di configurazione"""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Errore: File {CONFIG_FILE} non trovato")
        return None
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError:
        print(f"❌ Errore: File {CONFIG_FILE} non è un JSON valido")
        return None
    except Exception as e:
        print(f"❌ Errore durante il caricamento della configurazione: {e}")
        return None

def load_first_account(config):
    """Carica il primo account dal file di configurazione JSON"""
    if not config:
        return None, None
    
    if not config.get("accounts") or len(config["accounts"]) == 0:
        print("❌ Errore: Nessun account trovato nel file di configurazione")
        return None, None
    
    account = config["accounts"][0]
    email = account.get("email")
    password = account.get("password")
    
    if not email or not password:
        print("❌ Errore: Email o password mancanti per il primo account")
        return None, None
    
    # Estrai anche altri parametri dall'account (se presenti)
    visa_type = account.get("visa_type", "Study Visa (D)")
    visa_id = 8  # default Study Visa (D)
    
    # Converte il nome del visto in ID usando constants
    try:
        from constants import VISA_TYPES
        visa_id = VISA_TYPES.get(visa_type, 8)
    except:
        pass
    
    office = account.get("office_id", "Cairo")
    office_id = 1  # default Cairo
    try:
        from constants import OFFICES
        office_id = OFFICES.get(office, 1)
    except:
        pass
    
    all_offices = account.get("all_offices", True)
    service_level_id = int(account.get("service_level_id", 1))
    trip_date = account.get("trip_date", "")
    persons = int(account.get("persons", 1)) if account.get("persons") else 1
    destination = account.get("destination", "")
    
    print(f"✅ Caricato account: {email}")
    print(f"   - Tipo visto: {visa_type} (ID: {visa_id})")
    print(f"   - Ufficio: {office} (ID: {office_id})")
    print(f"   - Tutti gli uffici: {all_offices}")
    print(f"   - Service Level: {service_level_id}")
    if trip_date:
        print(f"   - Data viaggio: {trip_date}")
    if destination:
        print(f"   - Destinazione: {destination}")
    if persons > 1:
        print(f"   - Persone: {persons}")
    
    return email, password, visa_id, office_id, service_level_id, trip_date, persons, destination, all_offices

# ==================== CARICA CONFIGURAZIONI ====================
config_data = load_config_from_file()
if not config_data:
    print("Impossibile proseguire. Verifica che almaviva_config.json esista e sia valido.")
    exit(1)

EMAIL, PASSWORD, VISA_ID, OFFICE_ID, SERVICE_LEVEL, TRIP_DATE, PERSONS, DESTINATION, ALL_OFFICES = load_first_account(config_data)

if not EMAIL or not PASSWORD:
    print("Impossibile proseguire. Verifica che almaviva_config.json contenga un account valido.")
    exit(1)

# Imposta la data di viaggio (se non presente, usa tra 30 giorni)
if not TRIP_DATE:
    TRIP_DATE = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

# Imposta intervallo dalle impostazioni globali (default 5 minuti)
CHECK_INTERVAL_SEC = config_data.get("settings", {}).get("check_interval_min", 5) * 60

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

def check_availability(token, office_id, visa_id, service_level):
    url = f"{CHECKS_URL}?officeId={office_id}&visaId={visa_id}&serviceLevelId={service_level}"
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

def get_free_slots(token, office_id, date, quantity=1):
    url = f"{FREE_SLOTS_URL}?officeId={office_id}&quantity={quantity}&date={date}&type=WEB"
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
    
    print(f"\n{'='*50}")
    print(f"💰 Account: {EMAIL}")
    print(f"🎯 Visto ID: {VISA_ID}")
    print(f"🏢 Ufficio ID: {OFFICE_ID}")
    print(f"🔄 Intervallo: {CHECK_INTERVAL_SEC // 60} minuti")
    print(f"📅 Data di riferimento: {TRIP_DATE}")
    if ALL_OFFICES:
        print(f"🏢 Controllo: Tutti gli uffici (Cairo e Alessandria)")
    else:
        print(f"🏢 Controllo: Solo ufficio {OFFICE_ID}")
    print(f"{'='*50}\n")
    
    print(f"🚀 Inizio monitoraggio... (Ctrl+C per fermare)")
    
    # Determina quali uffici controllare
    office_ids = [1, 2] if ALL_OFFICES else [OFFICE_ID]
    
    while True:
        for office_id in office_ids:
            result = check_availability(token, office_id, VISA_ID, SERVICE_LEVEL)
            
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
                office_name = "Cairo" if office_id == 1 else "Alessandria"
                print(f"✅ Disponibilità rilevata per office {office_id} ({office_name})! Recupero slot...")
                slots = get_free_slots(token, office_id, TRIP_DATE, quantity=PERSONS)
                if slots == "expired":
                    continue
                if slots == "rate_limit":
                    time.sleep(60)
                    continue
                if slots and len(slots) > 0:
                    print(f"🎯 Slot trovati per {TRIP_DATE}: {slots}")
                    print(f"🏆 Appuntamento disponibile! Vai su https://egy.almaviva-visa.it")
                    return
                else:
                    print(f"Nessuno slot per la data {TRIP_DATE}, continuo...")
            else:
                office_name = "Cairo" if office_id == 1 else "Alessandria"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Nessun appuntamento (office {office_id} - {office_name})")
        
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Monitoraggio fermato dall'utente")