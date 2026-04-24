#!/usr/bin/env python3
import customtkinter as ctk
import tkinter.messagebox as msgbox
import threading
import time
from datetime import datetime, timedelta
from constants import VISA_TYPES, OFFICES, DEFAULT_CHECK_INTERVAL_MIN, REQUEST_DELAY_SECONDS, OFFICE_HOURS_START, OFFICE_HOURS_END
from config import load_config, save_config
from notifier import send_telegram
from api_client import AlmavivaAPIClient
from browser_automation import BrowserAutomation
from utils import log_message, parse_iso_slot, wait_seconds

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AlmavivaBotThread:
    def __init__(self, account, settings, log_callback):
        self.account = account
        self.settings = settings
        self.log_callback = log_callback
        self.running = False
        self.thread = None
        self.browser = None
        self.api = None

    def log(self, msg):
        log_message(self.log_callback, msg)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.browser:
            self.browser.quit()

    def _monitor(self):
        self.browser = BrowserAutomation(
            self.account,
            headless=self.settings.get("headless", False),
            log_callback=self.log
        )
        if not self.browser.login():
            self.log("Login fallito, bot fermo.")
            self.running = False
            return
        token = self.browser.token
        if not token:
            self.log("Token non disponibile, fermo.")
            self.running = False
            return

        self.api = AlmavivaAPIClient(token, log_callback=self.log)

        visa_name = self.account.get("visa_type")
        visa_id = VISA_TYPES.get(visa_name, 8)
        service_level = int(self.account.get("service_level_id", 1))
        trip_date = self.account.get("trip_date")
        if not trip_date:
            trip_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        all_offices = self.account.get("all_offices", True)
        office_ids = [1, 2] if all_offices else [OFFICES.get(self.account.get("office_id", "Cairo"), 1)]
        interval_min = self.settings.get("check_interval_min", DEFAULT_CHECK_INTERVAL_MIN)

        self.log(f"Monitoraggio avviato: uffici={office_ids}, visto={visa_name}, data={trip_date}, intervallo={interval_min} min, delay={REQUEST_DELAY_SECONDS}s")
        self.log(f"Controllo attivo solo nell'orario {OFFICE_HOURS_START}:00 - {OFFICE_HOURS_END}:00.")

        while self.running:
            try:
                # Attendi orario ufficio
                now = datetime.now()
                start_time = now.replace(hour=OFFICE_HOURS_START, minute=0, second=0, microsecond=0)
                end_time = now.replace(hour=OFFICE_HOURS_END, minute=0, second=0, microsecond=0)
                if now < start_time:
                    wait_seconds((start_time - now).total_seconds())
                elif now > end_time:
                    tomorrow_start = start_time + timedelta(days=1)
                    wait_seconds((tomorrow_start - now).total_seconds())

                for office_id in office_ids:
                    if not self.running:
                        break
                    try:
                        avail = self.api.check_availability(office_id, visa_id, service_level)
                        wait_seconds(REQUEST_DELAY_SECONDS)
                        if avail is True:
                            self.log(f"✅ Disponibilità per office {office_id}, recupero slot...")
                            slots = self.api.get_free_slots(office_id, trip_date)
                            wait_seconds(REQUEST_DELAY_SECONDS)
                            if slots and len(slots) > 0:
                                iso = slots[0]
                                d, t = parse_iso_slot(iso)
                                if not d:
                                    d = trip_date
                                    t = "orario non specificato"
                                office_name = "Cairo" if office_id == 1 else "Alessandria"
                                msg = f"✅ APPUNTAMENTO TROVATO!\nUfficio: {office_name}\nData: {d}\nOra: {t}"
                                bot_token = self.settings.get("telegram_bot_token")
                                chat_id = self.settings.get("telegram_chat_id")
                                if bot_token and chat_id:
                                    send_telegram(bot_token, chat_id, msg, self.log)
                                self.log(msg)
                                self.running = False
                                break
                            else:
                                self.log(f"⚠️ Disponibilità ma nessuno slot per la data {trip_date}")
                        else:
                            self.log(f"Nessuno slot - office {office_id} - {datetime.now().strftime('%H:%M:%S')}")
                    except Exception as e:
                        if "rate_limit" in str(e) or "429" in str(e):
                            self.log("Rate limit (429), attendo 60 secondi")
                            wait_seconds(60)
                        elif "rate_limit_account" in str(e):
                            self.log("Limite account raggiunto, attendo 30 minuti")
                            wait_seconds(30 * 60)
                            continue
                        else:
                            self.log(f"Errore office {office_id}: {e}")
                    wait_seconds(5)
                if self.running:
                    now_hour = datetime.now().hour
                    if OFFICE_HOURS_START <= now_hour < OFFICE_HOURS_END:
                        wait_seconds(interval_min * 60)
                    else:
                        self.log("Orario ufficio terminato, attendo prossimo ciclo...")
            except Exception as e:
                self.log(f"Errore nel loop: {e}")
                wait_seconds(60)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Almaviva Bot")
        self.geometry("800x600")
        self.config = load_config()
        self.bots = {}
        self._create_widgets()

    def _log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")

    def _create_widgets(self):
        self.log_text = ctk.CTkTextbox(self, height=400)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        btn_start = ctk.CTkButton(self, text="Avvia Monitoraggio", command=self.start_monitor)
        btn_start.pack(pady=5)
        btn_stop = ctk.CTkButton(self, text="Ferma", fg_color="red", command=self.stop_all)
        btn_stop.pack(pady=5)

    def start_monitor(self):
        if not self.config["accounts"]:
            self._log("Nessun account configurato")
            return
        acc = self.config["accounts"][0]
        bot = AlmavivaBotThread(acc, self.config["settings"], self._log)
        bot.start()
        self.bots[acc["name"]] = bot

    def stop_all(self):
        for bot in self.bots.values():
            bot.stop()
        self.bots.clear()

if __name__ == "__main__":
    app = App()
    app.mainloop()