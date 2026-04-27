#!/usr/bin/env python3
"""
Almaviva Bot - CLI Engine
Monitoraggio appuntamenti per singolo account con gestione automatica limiti.
Supporto proxy e parallelizzazione degli uffici. Salva contatori su file separato per account.
"""
import argparse
import sys
import time
import json
import os
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from constants import AUTH_TOKEN_URL, CLIENT_ID, CHECKS_URL, FREE_SLOTS_URL, VISA_TYPES, OFFICES

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

class RateLimiter:
    def __init__(self, email, session_limit=28, daily_limit=70):
        self.email = email
        self.session_limit = session_limit
        self.daily_limit = daily_limit
        self.session_requests = 0
        self.daily_requests = 0
        self.session_reset = time.time() + 1800
        self.daily_reset = time.time() + 86400
        # Crea un nome file sicuro dall'email
        safe_email = email.replace('@', '_').replace('.', '_')
        self.counters_file = f"request_counters_{safe_email}.json"
        self._load()

    def _load(self):
        if os.path.exists(self.counters_file):
            try:
                with open(self.counters_file, "r") as f:
                    data = json.load(f)
                if data.get("email") == self.email:
                    self.session_requests = data.get("session_requests", 0)
                    self.daily_requests = data.get("daily_requests", 0)
                    self.session_reset = data.get("session_reset", time.time() + 1800)
                    self.daily_reset = data.get("daily_reset", time.time() + 86400)
                    log(f"📊 Contatori caricati: sessione {self.session_requests}/{self.session_limit}, giorno {self.daily_requests}/{self.daily_limit}")
            except:
                pass

    def _save(self):
        try:
            with open(self.counters_file, "w") as f:
                json.dump({
                    "email": self.email,
                    "session_requests": self.session_requests,
                    "daily_requests": self.daily_requests,
                    "session_reset": self.session_reset,
                    "daily_reset": self.daily_reset
                }, f)
        except:
            pass

    def _check_reset(self):
        now = time.time()
        if now >= self.session_reset:
            self.session_requests = 0
            self.session_reset = now + 1800
            log("🔄 Reset contatore sessione (30 min)")
        if now >= self.daily_reset:
            self.daily_requests = 0
            self.daily_reset = now + 86400
            log("🔄 Reset contatore giornaliero")
        self._save()

    def wait_if_needed(self):
        self._check_reset()
        if self.session_requests >= self.session_limit:
            wait = self.session_reset - time.time()
            log(f"⏳ Limite sessione ({self.session_requests}/{self.session_limit}). Attendo {int(wait//60)} minuti.")
            time.sleep(wait)
            self.session_requests = 0
            self._save()
        if self.daily_requests >= self.daily_limit:
            wait = self.daily_reset - time.time()
            log(f"⏳ Limite giornaliero ({self.daily_requests}/{self.daily_limit}). Attendo {int(wait//3600)} ore.")
            time.sleep(wait)
            self.daily_requests = 0
            self._save()

    def increment(self):
        self.session_requests += 1
        self.daily_requests += 1
        self._save()
        log(f"📊 Richieste: sessione {self.session_requests}/{self.session_limit}, giorno {self.daily_requests}/{self.daily_limit}")

# ==================== FUNZIONI API ====================
def get_token(email, password, session):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": email,
        "password": password
    }
    try:
        r = session.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
        if r.status_code != 200:
            log(f"❌ Login fallito: {r.status_code}")
            return None, None
        token_data = r.json()
        log("✅ Token ottenuto")
        return token_data["access_token"], token_data.get("refresh_token")
    except Exception as e:
        log(f"❌ Errore login: {e}")
        return None, None

def refresh_token(refresh_token_value, session):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token_value
    }
    try:
        r = session.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

def check_availability(token, office_id, visa_id, service_level, rate_limiter, session):
    rate_limiter.wait_if_needed()
    url = f"{CHECKS_URL}?officeId={office_id}&visaId={visa_id}&serviceLevelId={service_level}"
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.now()
    try:
        r = session.get(url, headers=headers, timeout=15)
        elapsed = (datetime.now() - start).total_seconds()
        if r.status_code == 401:
            return "expired", elapsed, r.status_code
        if r.status_code == 429:
            return "rate_limit", elapsed, r.status_code
        if r.status_code == 400:
            # Leggi il corpo della risposta
            try:
                error_data = r.json()
                message = error_data.get("message", "Nessun dettaglio")
                log(f"❌ ERRORE 400: {message}")
            except:
                log(f"❌ ERRORE 400: {r.text}")
            return False, elapsed, r.status_code
        r.raise_for_status()
        rate_limiter.increment()
        return r.json(), elapsed, r.status_code
    except Exception as e:
        log(f"Errore check: {e}")
        rate_limiter.increment()
        return False, None, None

def get_free_slots(token, office_id, date, quantity, rate_limiter, session):
    rate_limiter.wait_if_needed()
    url = f"{FREE_SLOTS_URL}?officeId={office_id}&quantity={quantity}&date={date}&type=WEB"
    headers = {"Authorization": f"Bearer {token}"}
    start = datetime.now()
    try:
        r = session.get(url, headers=headers, timeout=15)
        elapsed = (datetime.now() - start).total_seconds()
        if r.status_code == 401:
            return "expired", elapsed, r.status_code
        if r.status_code == 429:
            return "rate_limit", elapsed, r.status_code
        if r.status_code == 400:
            # Leggi il corpo della risposta
            try:
                error_data = r.json()
                message = error_data.get("message", "Nessun dettaglio")
                log(f"❌ ERRORE 400: {message}")
            except:
                log(f"❌ ERRORE 400: {r.text}")
            return False, elapsed, r.status_code
        r.raise_for_status()
        rate_limiter.increment()
        return r.json(), elapsed, r.status_code
    except Exception as e:
        log(f"Errore slots: {e}")
        rate_limiter.increment()
        return [], None, None

def send_telegram(bot_token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        with requests.Session() as sess:
            r = sess.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            return r.status_code == 200
    except Exception as e:
        log(f"Errore invio Telegram: {e}")
        return False

def get_current_ip(session):
    try:
        r = session.get("https://api.ipify.org", timeout=5)
        return r.text.strip()
    except:
        return "sconosciuto"

def process_office(office_id, token, trip_date, args, rate_limiter, session):
    office_name = "Cairo" if office_id == 1 else "Alessandria"
    result, elapsed_check, status_check = check_availability(token, office_id, args.visa_id, args.service_level, rate_limiter, session)
    if result == "expired":
        return {"status": "expired"}
    if result == "rate_limit":
        return {"status": "rate_limit"}
    if result is True:
        slots, elapsed_slots, status_slots = get_free_slots(token, office_id, trip_date, args.persons, rate_limiter, session)
        if slots and len(slots) > 0:
            rtt_check_ms = elapsed_check * 1000 if elapsed_check is not None else None
            rtt_slots_ms = elapsed_slots * 1000 if elapsed_slots is not None else None
            return {
                "status": "available",
                "office_name": office_name,
                "slots": slots,
                "elapsed_check": elapsed_check,
                "elapsed_slots": elapsed_slots,
                "status_check": status_check,
                "status_slots": status_slots,
                "rtt_check_ms": rtt_check_ms,
                "rtt_slots_ms": rtt_slots_ms
            }
        else:
            return {"status": "nothing"}
    return {"status": "nothing"}

def sleep_between_requests(delay_sec):
    if delay_sec <= 0:
        return
    jitter = random.uniform(0.8, 1.2)
    time.sleep(delay_sec * jitter)

def main():
    parser = argparse.ArgumentParser(description='Almaviva Bot CLI Engine')
    parser.add_argument('--email', required=True, help='Email account')
    parser.add_argument('--password', required=True, help='Password')
    parser.add_argument('--account-name', default='', help='Nome visualizzato dell\'account')
    parser.add_argument('--visa-id', type=int, default=8, help='Visa ID')
    parser.add_argument('--office-ids', default='1,2', help='Uffici (es. 1,2)')
    parser.add_argument('--trip-date', help='Data viaggio (YYYY-MM-DD)')
    parser.add_argument('--interval-sec', type=int, default=300, help='Intervallo tra cicli (secondi)')
    parser.add_argument('--delay-sec', type=int, default=0, help='Pausa tra richieste (secondi)')
    parser.add_argument('--telegram-token', default='', help='Token bot Telegram')
    parser.add_argument('--telegram-chat', default='', help='Chat ID Telegram')
    parser.add_argument('--service-level', type=int, default=1, help='Service level ID')
    parser.add_argument('--persons', type=int, default=1, help='Numero persone')
    parser.add_argument('--destination', default='', help='Destinazione')
    parser.add_argument('--bot-name', default='Almaviva Bot', help='Nome del bot per le notifiche')
    parser.add_argument('--proxy', default='', help='Proxy in formato host:port:user:pass (opzionale)')
    args = parser.parse_args()

    session = requests.Session()
    if args.proxy:
        parts = args.proxy.split(':')
        if len(parts) >= 2:
            host = parts[0]; port = parts[1]; user = parts[2] if len(parts)>2 else ""; pwd = parts[3] if len(parts)>3 else ""
            proxy_url = f"http://{host}:{port}"
            if user and pwd: proxy_url = f"http://{user}:{pwd}@{host}:{port}"
            session.proxies.update({"http": proxy_url, "https": proxy_url})
            log(f"🌐 Proxy configurato: {host}:{port}")
        else:
            log("⚠️ Formato proxy non valido, ignoro.")

    office_ids = [int(x) for x in args.office_ids.split(',')]
    trip_date = args.trip_date or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    interval_sec = args.interval_sec
    delay_sec = args.delay_sec

    visa_name = "Sconosciuto"
    for name, vid in VISA_TYPES.items():
        if vid == args.visa_id: visa_name = name; break

    display_name = args.account_name if args.account_name else args.email

    log(f"Avvio monitoraggio per {display_name}")
    log(f"Visto ID: {args.visa_id} ({visa_name}), Uffici: {office_ids}, Data viaggio: {trip_date}")
    log(f"Intervallo: {interval_sec} secondi")
    if delay_sec > 0:
        log(f"Delay tra richieste: {delay_sec} secondi")

    rate_limiter = RateLimiter(args.email)
    token, refresh = get_token(args.email, args.password, session)
    if not token:
        return 1

    current_ip = get_current_ip(session)

    # Modalità sequenziale o parallela in base al delay
    while True:
        if delay_sec > 0:
            for office_id in office_ids:
                result = process_office(office_id, token, trip_date, args, rate_limiter, session)
                if result["status"] == "expired":
                    log("Token scaduto, rinnovo...")
                    if refresh:
                        new_data = refresh_token(refresh, session)
                        if new_data:
                            token = new_data["access_token"]
                            refresh = new_data.get("refresh_token")
                            log("Token rinnovato")
                            break
                    else:
                        token, refresh = get_token(args.email, args.password, session)
                        if not token: time.sleep(60)
                        break
                elif result["status"] == "rate_limit":
                    log("Rate limit (429), attendo 60 secondi")
                    time.sleep(60)
                    break
                elif result["status"] == "available":
                    office_name = result["office_name"]
                    slots = result["slots"]
                    elapsed_check = result["elapsed_check"]
                    elapsed_slots = result["elapsed_slots"]
                    status_check = result["status_check"]
                    status_slots = result["status_slots"]
                    rtt_check_ms = result["rtt_check_ms"]
                    rtt_slots_ms = result["rtt_slots_ms"]

                    speed_check = f"{elapsed_check:.3f}s" if elapsed_check is not None else "N/A"
                    speed_slots = f"{elapsed_slots:.3f}s" if elapsed_slots is not None else "N/A"

                    msg = f"<b>🎯 <u>SLOT TROVATO PER {display_name}</u></b> 🎯\n"
                    msg += f"=================================\n"
                    msg += f"<b>🤖 Bot:</b> {args.bot_name}\n"
                    msg += f"<b>📧 Email:</b> {args.email}\n"
                    msg += f"<b>🏢 Centro:</b> {office_name}\n"
                    msg += f"<b>🎫 Visto:</b> {visa_name} (ID {args.visa_id})\n"
                    msg += f"<b>📅 Data viaggio:</b> {trip_date}\n"
                    msg += f"<b>⏰ Slot:</b> {slots[0]}\n"
                    msg += f"<b>🌐 IP:</b> {current_ip}\n"
                    msg += f"<b>📤 Richiesta inviata:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                    msg += f"<b>⚡ Velocità /checks:</b> {speed_check} (status {status_check})\n"
                    msg += f"<b>⚡ Velocità /free:</b> {speed_slots} (status {status_slots})\n"
                    if rtt_check_ms is not None:
                        msg += f"<b>📊 RTT /checks:</b> {rtt_check_ms:.0f} ms (status {status_check})\n"
                    if rtt_slots_ms is not None:
                        msg += f"<b>📊 RTT /free:</b> {rtt_slots_ms:.0f} ms (status {status_slots})\n"
                    msg += f"<b>⏱️ Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    msg += f"=================================\n"
                    msg += f"\nBY Ibrahim ALI"

                    log(f"Notifica inviata per {display_name}")
                    if args.telegram_token and args.telegram_chat:
                        send_telegram(args.telegram_token, args.telegram_chat, msg)
                        log("✅ Notifica Telegram inviata")
                    else:
                        log("⚠️ Telegram non configurato, notifica non inviata")
                    return 0
                sleep_between_requests(delay_sec)
        else:
            # Modalità parallela
            with ThreadPoolExecutor(max_workers=len(office_ids)) as executor:
                futures = {executor.submit(process_office, oid, token, trip_date, args, rate_limiter, session): oid for oid in office_ids}
                for future in as_completed(futures):
                    result = future.result()
                    if result["status"] == "expired":
                        log("Token scaduto, rinnovo...")
                        if refresh:
                            new_data = refresh_token(refresh, session)
                            if new_data:
                                token = new_data["access_token"]
                                refresh = new_data.get("refresh_token")
                                log("Token rinnovato")
                                break
                        else:
                            token, refresh = get_token(args.email, args.password, session)
                            if not token: time.sleep(60)
                            break
                    elif result["status"] == "rate_limit":
                        log("Rate limit (429), attendo 60 secondi")
                        time.sleep(60)
                        break
                    elif result["status"] == "available":
                        office_name = result["office_name"]
                        slots = result["slots"]
                        elapsed_check = result["elapsed_check"]
                        elapsed_slots = result["elapsed_slots"]
                        status_check = result["status_check"]
                        status_slots = result["status_slots"]
                        rtt_check_ms = result["rtt_check_ms"]
                        rtt_slots_ms = result["rtt_slots_ms"]

                        speed_check = f"{elapsed_check:.3f}s" if elapsed_check is not None else "N/A"
                        speed_slots = f"{elapsed_slots:.3f}s" if elapsed_slots is not None else "N/A"

                        msg = f"<b>🎯 <u>SLOT TROVATO PER {display_name}</u></b> 🎯\n"
                        msg += f"=================================\n"
                        msg += f"<b>🤖 Bot:</b> {args.bot_name}\n"
                        msg += f"<b>📧 Email:</b> {args.email}\n"
                        msg += f"<b>🏢 Centro:</b> {office_name}\n"
                        msg += f"<b>🎫 Visto:</b> {visa_name} (ID {args.visa_id})\n"
                        msg += f"<b>📅 Data viaggio:</b> {trip_date}\n"
                        msg += f"<b>⏰ Slot:</b> {slots[0]}\n"
                        msg += f"<b>🌐 IP:</b> {current_ip}\n"
                        msg += f"<b>📤 Richiesta inviata:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                        msg += f"<b>⚡ Velocità /checks:</b> {speed_check} (status {status_check})\n"
                        msg += f"<b>⚡ Velocità /free:</b> {speed_slots} (status {status_slots})\n"
                        if rtt_check_ms is not None:
                            msg += f"<b>📊 RTT /checks:</b> {rtt_check_ms:.0f} ms (status {status_check})\n"
                        if rtt_slots_ms is not None:
                            msg += f"<b>📊 RTT /free:</b> {rtt_slots_ms:.0f} ms (status {status_slots})\n"
                        msg += f"<b>⏱️ Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        msg += f"=================================\n"
                        msg += f"\nBY Ibrahim ALI"

                        log(f"Notifica inviata per {display_name}")
                        if args.telegram_token and args.telegram_chat:
                            send_telegram(args.telegram_token, args.telegram_chat, msg)
                            log("✅ Notifica Telegram inviata")
                        else:
                            log("⚠️ Telegram non configurato, notifica non inviata")
                        return 0
        time.sleep(interval_sec)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Interrotto dall'utente")
        sys.exit(0)