#!/usr/bin/env python3
import customtkinter as ctk
import tkinter.messagebox as msgbox
import threading
import time
from datetime import datetime, timedelta
from constants import VISA_TYPES, OFFICES, DEFAULT_CHECK_INTERVAL_MIN, REQUEST_DELAY_SECONDS, OFFICE_HOURS_START, OFFICE_HOURS_END
from config import load_config, save_config
from proxy_manager import ProxyManager
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

        proxy_mgr = ProxyManager(self.settings)
        self.api = AlmavivaAPIClient(token, proxy_mgr, log_callback=self.log)

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
        self.title("Almaviva Bot - Con Proxy")
        self.geometry("1000x700")
        self.config = load_config()
        self.bots = {}
        self._create_widgets()
        self._populate_proxy_fields_from_config()

    def _populate_proxy_fields_from_config(self):
        proxy_list = self.config["settings"].get("proxy_list", [])
        if proxy_list:
            first_proxy = proxy_list[0]
            parts = first_proxy.split(':')
            if len(parts) >= 2:
                self.proxy_host.delete(0, 'end')
                self.proxy_host.insert(0, parts[0])
                self.proxy_port.delete(0, 'end')
                self.proxy_port.insert(0, parts[1])
                if len(parts) >= 4:
                    self.proxy_user.delete(0, 'end')
                    self.proxy_user.insert(0, parts[2])
                    self.proxy_pass.delete(0, 'end')
                    self.proxy_pass.insert(0, parts[3])

    def _log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Sezione Account
        ctk.CTkLabel(left, text="ACCOUNT", font=("Arial",16,"bold")).pack(pady=(10,5))
        self.account_list = ctk.CTkComboBox(left, values=[], width=250)
        self.account_list.pack(pady=5)
        btn_frame = ctk.CTkFrame(left)
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Nuovo", width=60, command=self.add_account).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Modifica", width=60, command=self.edit_account).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Elimina", width=60, command=self.delete_account).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Avvia", fg_color="green", width=80, command=self.start_monitor).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Ferma", fg_color="red", width=80, command=self.stop_all).pack(side="left", padx=2)

        # Sezione Proxy
        ctk.CTkLabel(left, text="PROXY (OPZIONALE)", font=("Arial",14,"bold")).pack(pady=(15,5))
        self.proxy_enabled = ctk.BooleanVar(value=self.config["settings"].get("proxy_enabled", False))
        ctk.CTkCheckBox(left, text="Abilita proxy", variable=self.proxy_enabled).pack(anchor="w", padx=20)
        
        ctk.CTkLabel(left, text="Host (es. proxy.smartproxy.net)").pack(anchor="w", padx=20)
        self.proxy_host = ctk.CTkEntry(left, width=250)
        self.proxy_host.pack(pady=2, padx=20)
        
        ctk.CTkLabel(left, text="Porta").pack(anchor="w", padx=20)
        self.proxy_port = ctk.CTkEntry(left, width=250)
        self.proxy_port.pack(pady=2, padx=20)
        
        ctk.CTkLabel(left, text="Username (opzionale)").pack(anchor="w", padx=20)
        self.proxy_user = ctk.CTkEntry(left, width=250)
        self.proxy_user.pack(pady=2, padx=20)
        
        ctk.CTkLabel(left, text="Password (opzionale)").pack(anchor="w", padx=20)
        self.proxy_pass = ctk.CTkEntry(left, width=250, show="*")
        self.proxy_pass.pack(pady=2, padx=20)
        
        ctk.CTkButton(left, text="Test Proxy", command=self.test_proxy).pack(pady=5)

        # Sezione Impostazioni
        ctk.CTkLabel(left, text="IMPOSTAZIONI", font=("Arial",14,"bold")).pack(pady=(15,5))
        self.interval = ctk.CTkEntry(left, width=100)
        self.interval.insert(0, str(self.config["settings"].get("check_interval_min", DEFAULT_CHECK_INTERVAL_MIN)))
        ctk.CTkLabel(left, text="Intervallo (minuti)").pack(anchor="w", padx=20)
        self.interval.pack(anchor="w", padx=20)
        
        self.headless_var = ctk.BooleanVar(value=self.config["settings"].get("headless", False))
        ctk.CTkCheckBox(left, text="Modalità Headless (browser invisibile)", variable=self.headless_var).pack(anchor="w", padx=20)

        # Sezione Telegram
        ctk.CTkLabel(left, text="TELEGRAM NOTIFICHE", font=("Arial",14,"bold")).pack(pady=(15,5))
        self.tg_token = ctk.CTkEntry(left, width=250)
        self.tg_token.insert(0, self.config["settings"].get("telegram_bot_token", ""))
        ctk.CTkLabel(left, text="Bot Token").pack(anchor="w", padx=20)
        self.tg_token.pack(pady=2, padx=20)
        
        self.tg_chat = ctk.CTkEntry(left, width=250)
        self.tg_chat.insert(0, self.config["settings"].get("telegram_chat_id", ""))
        ctk.CTkLabel(left, text="Chat ID").pack(anchor="w", padx=20)
        self.tg_chat.pack(pady=2, padx=20)

        ctk.CTkButton(left, text="Salva impostazioni", command=self.save_settings).pack(pady=10)

        # Sezione Log
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(right, text="LOG", font=("Arial",16,"bold")).pack(pady=5)
        self.log_text = ctk.CTkTextbox(right, height=600)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_account_list()

    def refresh_account_list(self):
        names = [acc.get("name", "Senza nome") for acc in self.config.get("accounts", [])]
        self.account_list.configure(values=names)
        if names:
            self.account_list.set(names[0])

    def add_account(self):
        self.open_account_editor()

    def edit_account(self):
        selected = self.account_list.get()
        if selected:
            acc = next((a for a in self.config["accounts"] if a.get("name") == selected), None)
            if acc:
                self.open_account_editor(acc)

    def open_account_editor(self, account=None):
        editor = ctk.CTkToplevel(self)
        editor.title("Account Editor")
        editor.geometry("750x700")
        scroll_frame = ctk.CTkScrollableFrame(editor, width=700, height=600)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        entries = {}
        fields = [
            ("name", "Nome account *"),
            ("first_name", "Nome"),
            ("last_name", "Cognome"),
            ("email", "Email *"),
            ("password", "Password *"),
            ("birth_date", "Data nascita (YYYY-MM-DD)"),
            ("gender", "Sesso (M/F)"),
            ("nationality", "Nazionalità"),
            ("residence", "Residenza"),
            ("passport_number", "Numero passaporto"),
            ("passport_issue_date", "Data rilascio (YYYY-MM-DD)"),
            ("passport_country", "Paese rilascio"),
            ("passport_expiry", "Data scadenza (YYYY-MM-DD)"),
            ("phone", "Telefono"),
            ("trip_date", "Data viaggio (YYYY-MM-DD)"),
            ("destination", "Destinazione"),
            ("service_level_id", "Service Level ID (1)"),
            ("persons", "Numero persone (default 1)"),
        ]
        row = 0
        for key, label in fields:
            ctk.CTkLabel(scroll_frame, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            entry = ctk.CTkEntry(scroll_frame, width=350)
            entry.grid(row=row, column=1, padx=5, pady=5)
            if account and key in account:
                entry.insert(0, account[key])
            entries[key] = entry
            row += 1

        # Tipo visto
        ctk.CTkLabel(scroll_frame, text="Tipo visto *").grid(row=row, column=0, padx=5, pady=5, sticky="w")
        visa_combo = ctk.CTkComboBox(scroll_frame, values=list(VISA_TYPES.keys()), width=350)
        visa_combo.grid(row=row, column=1, padx=5, pady=5)
        if account and "visa_type" in account:
            visa_combo.set(account["visa_type"])
        else:
            visa_combo.set(list(VISA_TYPES.keys())[0])
        entries["visa_type"] = visa_combo
        row += 1

        # Uffici
        all_offices_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(scroll_frame, text="Tutti gli uffici (Cairo e Alessandria)", variable=all_offices_var).grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        entries["all_offices"] = all_offices_var
        row += 1

        ctk.CTkLabel(scroll_frame, text="Ufficio specifico (se non tutti)").grid(row=row, column=0, padx=5, pady=5, sticky="w")
        office_combo = ctk.CTkComboBox(scroll_frame, values=list(OFFICES.keys()), width=350)
        office_combo.grid(row=row, column=1, padx=5, pady=5)
        office_combo.set("Cairo")
        entries["office_id"] = office_combo
        row += 1

        def update_office():
            if all_offices_var.get():
                office_combo.configure(state="disabled")
            else:
                office_combo.configure(state="normal")
        all_offices_var.trace_add("write", lambda *_: update_office())
        update_office()

        def save():
            new_acc = {}
            for key in ["name", "first_name", "last_name", "email", "password", "birth_date",
                        "gender", "nationality", "residence", "passport_number", "passport_issue_date",
                        "passport_country", "passport_expiry", "phone", "trip_date", "destination",
                        "persons"]:
                val = entries.get(key)
                if val is not None:
                    new_acc[key] = val.get()
            try:
                new_acc["service_level_id"] = int(entries["service_level_id"].get())
            except:
                new_acc["service_level_id"] = 1
            new_acc["visa_type"] = entries["visa_type"].get()
            new_acc["all_offices"] = all_offices_var.get()
            if not new_acc["all_offices"]:
                new_acc["office_id"] = entries["office_id"].get()
            if not new_acc.get("name"):
                new_acc["name"] = new_acc.get("email", "unnamed")
            if account:
                for i, a in enumerate(self.config["accounts"]):
                    if a.get("name") == account["name"]:
                        self.config["accounts"][i] = new_acc
                        break
            else:
                self.config["accounts"].append(new_acc)
            save_config(self.config)
            self.refresh_account_list()
            editor.destroy()

        ctk.CTkButton(scroll_frame, text="Salva", command=save).grid(row=row, column=0, columnspan=2, pady=20)

    def delete_account(self):
        selected = self.account_list.get()
        if selected:
            self.config["accounts"] = [a for a in self.config["accounts"] if a.get("name") != selected]
            save_config(self.config)
            self.refresh_account_list()

    def save_settings(self):
        host = self.proxy_host.get().strip()
        port = self.proxy_port.get().strip()
        user = self.proxy_user.get().strip()
        pwd = self.proxy_pass.get().strip()
        proxy_list = []
        if host and port:
            if user and pwd:
                proxy_list.append(f"{host}:{port}:{user}:{pwd}")
            else:
                proxy_list.append(f"{host}:{port}")
        
        self.config["settings"]["proxy_list"] = proxy_list
        self.config["settings"]["proxy_enabled"] = self.proxy_enabled.get()
        self.config["settings"]["proxy_host"] = host
        self.config["settings"]["proxy_port"] = port
        self.config["settings"]["proxy_username"] = user
        self.config["settings"]["proxy_password"] = pwd
        self.config["settings"]["check_interval_min"] = int(self.interval.get())
        self.config["settings"]["headless"] = self.headless_var.get()
        self.config["settings"]["telegram_bot_token"] = self.tg_token.get()
        self.config["settings"]["telegram_chat_id"] = self.tg_chat.get()
        save_config(self.config)
        msgbox.showinfo("Info", "Impostazioni salvate")

    def test_proxy(self):
        host = self.proxy_host.get().strip()
        port = self.proxy_port.get().strip()
        user = self.proxy_user.get().strip()
        pwd = self.proxy_pass.get().strip()
        if not host or not port:
            msgbox.showerror("Errore", "Inserisci host e porta")
            return
        try:
            proxy_url = f"http://{host}:{port}"
            proxies = {"http": proxy_url, "https": proxy_url}
            if user and pwd:
                proxy_url_with_auth = f"http://{user}:{pwd}@{host}:{port}"
                proxies = {"http": proxy_url_with_auth, "https": proxy_url_with_auth}
            r = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=15)
            self._log(f"Test proxy riuscito: IP = {r.json().get('origin')}")
            msgbox.showinfo("Proxy OK", f"IP del proxy: {r.json().get('origin')}")
        except Exception as e:
            self._log(f"Test proxy fallito: {e}")
            msgbox.showerror("Proxy Fallito", str(e))

    def start_monitor(self):
        selected = self.account_list.get()
        if not selected:
            msgbox.showerror("Errore", "Seleziona un account")
            return
        acc = next((a for a in self.config["accounts"] if a.get("name") == selected), None)
        if not acc:
            return
        if selected in self.bots and self.bots[selected].running:
            msgbox.showinfo("Info", "Monitoraggio già attivo")
            return
        settings = self.config["settings"].copy()
        settings.update({
            "check_interval_min": int(self.interval.get()),
            "headless": self.headless_var.get(),
            "proxy_enabled": self.proxy_enabled.get(),
            "proxy_list": self.config["settings"].get("proxy_list", []),
            "telegram_bot_token": self.tg_token.get(),
            "telegram_chat_id": self.tg_chat.get(),
        })
        bot = AlmavivaBotThread(acc, settings, self._log)
        bot.start()
        self.bots[selected] = bot
        self._log(f"Avviato monitoraggio per {selected}")

    def stop_all(self):
        for name, bot in self.bots.items():
            bot.stop()
        self.bots.clear()
        self._log("Fermati tutti i monitoraggi")

if __name__ == "__main__":
    app = App()
    app.mainloop()