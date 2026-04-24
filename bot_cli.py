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

def check_availability(token):
    url = f"{CHECKS_URL}?officeId={OFFICE_ID}&visaId={VISA_ID}&serviceLevelId={SERVICE_LEVEL}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 401:
            print("Token scaduto, necessita refresh.")
            return None
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
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Errore slots: {e}")
        return []

def main():
    token = get_token()
    if not token:
        print("Impossibile proseguire. Verifica le credenziali.")
        return

    print(f"Inizio monitoraggio ogni {CHECK_INTERVAL_SEC} secondi...")
    target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"Data di riferimento: {target_date}")
    
    while True:
        is_available = check_availability(token)
        if is_available is None:
            print("Token scaduto, rinnovo...")
            token = get_token()
            if not token:
                print("Rinnovo fallito, riprovo tra 60 secondi.")
                time.sleep(60)
            continue

        if is_available is True:
            print("✅ Disponibilità rilevata! Recupero slot...")
            slots = get_free_slots(token, target_date)
            if slots:
                print(f"🎯 Slot trovati: {slots}")
                break
            else:
                print(f"Nessuno slot per la data {target_date}, continuo...")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nessun appuntamento.")

        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()