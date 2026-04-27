#!/usr/bin/env python3
import customtkinter as ctk
import tkinter.messagebox as msgbox
from tkinter import filedialog
import subprocess
import threading
import sys
import os
import json
from datetime import datetime
from constants import VISA_TYPES, OFFICES, DEFAULT_CHECK_INTERVAL_SEC, REQUEST_DELAY_SECONDS
from config import load_config, save_config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class BotProcess:
    # ... (identico a prima) ...
    def __init__(self, account, settings, log_callback):
        self.account = account
        self.settings = settings
        self.log_callback = log_callback
        self.process = None
        self.running = False

    def start(self):
        if self.running:
            return
        visa_name = self.account.get("visa_type", "Study Visa (D)")
        visa_id = VISA_TYPES.get(visa_name, 8)
        office_ids = [1, 2] if self.account.get("all_offices", True) else [OFFICES.get(self.account.get("office_id", "Cairo"), 1)]
        trip_date = self.account.get("trip_date", "")
        interval_sec = self.settings.get("check_interval_sec", DEFAULT_CHECK_INTERVAL_SEC)
        delay_sec = self.settings.get("request_delay_sec", REQUEST_DELAY_SECONDS)
        tg_token = self.settings.get("telegram_bot_token", "")
        tg_chat = self.settings.get("telegram_chat_id", "")
        service_level = int(self.account.get("service_level_id", 1))
        persons = int(self.account.get("persons", 1)) if self.account.get("persons") else 1
        email = self.account["email"]
        password = self.account["password"]
        account_name = self.account.get("name", email)

        account_proxy = self.account.get("proxy", "").strip()
        global_proxy_enabled = self.settings.get("proxy_enabled", False)
        global_proxy_list = self.settings.get("proxy_list", [])
        if account_proxy:
            proxy_string = account_proxy
        elif global_proxy_enabled and global_proxy_list:
            proxy_string = global_proxy_list[0]
        else:
            proxy_string = ""

        cmd = [
            sys.executable, "bot_cli.py",
            "--email", email,
            "--password", password,
            "--account-name", account_name,
            "--visa-id", str(visa_id),
            "--office-ids", ",".join(str(o) for o in office_ids),
            "--interval-sec", str(interval_sec),
            "--delay-sec", str(delay_sec),
            "--service-level", str(service_level),
            "--persons", str(persons),
            "--bot-name", "IBRA TECH BOT"
        ]
        if trip_date:
            cmd.extend(["--trip-date", trip_date])
        if tg_token and tg_chat:
            cmd.extend(["--telegram-token", tg_token, "--telegram-chat", tg_chat])
        if proxy_string:
            cmd.extend(["--proxy", proxy_string])
        # Nuove opzioni di sincronizzazione
        if self.settings.get("sync_mode", False):
            cmd.append("--sync-mode")
            cmd.extend(["--sync-interval", str(self.settings.get("sync_interval", 5))])

        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.running = True
        threading.Thread(target=self._read_output, daemon=True).start()
        self.log_callback(f"🚀 Avviato monitoraggio per {account_name} (PID {self.process.pid})")

    def _read_output(self):
        account_name = self.account.get('name', self.account['email'])
        for line in iter(self.process.stdout.readline, ''):
            if line:
                self.log_callback(f"[{account_name}] {line.strip()}")
        self.process.wait()
        self.running = False
        self.log_callback(f"🛑 Monitoraggio terminato per {account_name}")

    def stop(self):
        if self.process and self.running:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.running = False
            self.log_callback(f"🛑 Monitoraggio fermato per {self.account.get('name', self.account['email'])}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IBRA TECH BOT Controller")
        self.geometry("1300x800")
        self.minsize(1000, 600)
        self.config = load_config()
        self.processes = {}
        self.accounts_data = {}
        self._create_widgets()
        self._load_settings_into_ui()
        self._start_clock()
        self._start_counters_updater()

    def _start_clock(self):
        self.update_clock()

    def update_clock(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S") + f".{now.microsecond // 1000:03d}"
        self.title(f"IBRA TECH BOT Controller - {time_str}")
        self.after(10, self.update_clock)

    def _start_counters_updater(self):
        self.update_counters()
        self.after(5000, self._start_counters_updater)

    def update_counters(self):
        for acc in self.config.get("accounts", []):
            name = acc.get("name", "")
            email = acc.get("email", "")
            if not name:
                continue
            safe_email = email.replace('@', '_').replace('.', '_')
            counters_file = f"request_counters_{safe_email}.json"
            session_req = 0
            daily_req = 0
            if os.path.exists(counters_file):
                try:
                    with open(counters_file, "r") as f:
                        data = json.load(f)
                    session_req = data.get('session_requests', 0)
                    daily_req = data.get('daily_requests', 0)
                except:
                    pass
            self.accounts_data[name] = {"session": session_req, "daily": daily_req, "email": email}
        # Aggiorna la tabella
        for row, (name, data) in enumerate(self.accounts_data.items(), start=1):
            if name in self.table_labels:
                self.table_labels[name]["session"].configure(text=f"{data['session']}/28")
                self.table_labels[name]["daily"].configure(text=f"{data['daily']}/70")

    def _log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(self, width=380)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_propagate(False)

        settings_scroll = ctk.CTkScrollableFrame(left_frame, height=700)
        settings_scroll.pack(fill="both", expand=True)

        # LOGO
        logo_label = ctk.CTkLabel(settings_scroll, text="🤖 IBRA TECH BOT", font=("Arial", 20, "bold"))
        logo_label.pack(pady=(10,5))

        # TABELLA CONTATORI
        ctk.CTkLabel(settings_scroll, text="STATO ACCOUNT", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        self.table_frame = ctk.CTkFrame(settings_scroll)
        self.table_frame.pack(fill="x", padx=10, pady=5)
        headers = ["Account", "Email", "Sessione", "Giorno"]
        for col, txt in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=txt, font=("Arial", 11, "bold"))
            lbl.grid(row=0, column=col, padx=5, pady=2, sticky="ew")
        self.table_labels = {}
        for row, acc in enumerate(self.config.get("accounts", []), start=1):
            name = acc.get("name", "")
            email = acc.get("email", "")
            self.table_labels[name] = {}
            ctk.CTkLabel(self.table_frame, text=name).grid(row=row, column=0, padx=5, pady=2)
            ctk.CTkLabel(self.table_frame, text=email).grid(row=row, column=1, padx=5, pady=2)
            self.table_labels[name]["session"] = ctk.CTkLabel(self.table_frame, text="0/28")
            self.table_labels[name]["session"].grid(row=row, column=2, padx=5, pady=2)
            self.table_labels[name]["daily"] = ctk.CTkLabel(self.table_frame, text="0/70")
            self.table_labels[name]["daily"].grid(row=row, column=3, padx=5, pady=2)
        for col in range(4):
            self.table_frame.grid_columnconfigure(col, weight=1)

        # LISTA ACCOUNT CON CHECKBOX
        ctk.CTkLabel(settings_scroll, text="SELEZIONE ACCOUNT", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        self.account_checkbox_frame = ctk.CTkScrollableFrame(settings_scroll, height=150)
        self.account_checkbox_frame.pack(fill="x", padx=10, pady=5)
        self.account_checkboxes = {}
        self.refresh_checkbox_list()

        # PULSANTI
        btn_frame = ctk.CTkFrame(settings_scroll)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_frame, text="➕ Nuovo", width=80, command=self.add_account).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="✏️ Modifica", width=80, command=self.edit_account).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🗑️ Elimina", width=80, command=self.delete_account).pack(side="left", padx=2)

        action_frame = ctk.CTkFrame(settings_scroll)
        action_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(action_frame, text="▶ Avvia selezionati", fg_color="green", command=self.start_selected).pack(side="left", padx=2, expand=True, fill="x")
        ctk.CTkButton(action_frame, text="⏹ Ferma selezionati", fg_color="red", command=self.stop_selected).pack(side="left", padx=2, expand=True, fill="x")
        ctk.CTkButton(action_frame, text="⏸ Ferma tutti", fg_color="darkred", command=self.stop_all).pack(side="left", padx=2, expand=True, fill="x")

        # PROXY GLOBALE
        proxy_frame = ctk.CTkFrame(settings_scroll)
        proxy_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(proxy_frame, text="PROXY GLOBALE (opzionale)", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(5,0))
        self.proxy_host = ctk.CTkEntry(proxy_frame, placeholder_text="Host (es. proxy.smartproxy.net)")
        self.proxy_host.pack(fill="x", padx=10, pady=2)
        self.proxy_port = ctk.CTkEntry(proxy_frame, placeholder_text="Porta")
        self.proxy_port.pack(fill="x", padx=10, pady=2)
        self.proxy_user = ctk.CTkEntry(proxy_frame, placeholder_text="Username (opzionale)")
        self.proxy_user.pack(fill="x", padx=10, pady=2)
        self.proxy_pass = ctk.CTkEntry(proxy_frame, placeholder_text="Password (opzionale)", show="*")
        self.proxy_pass.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(proxy_frame, text="💾 Salva proxy globale", command=self.save_global_proxy).pack(pady=5)

        # IMPOSTAZIONI GLOBALI
        global_frame = ctk.CTkFrame(settings_scroll)
        global_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(global_frame, text="IMPOSTAZIONI GLOBALI", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(5,0))

        ctk.CTkLabel(global_frame, text="Intervallo tra cicli (secondi)").pack(anchor="w", padx=10)
        self.interval = ctk.CTkEntry(global_frame, width=120)
        self.interval.pack(anchor="w", padx=10, pady=2)

        ctk.CTkLabel(global_frame, text="Delay tra richieste (secondi)").pack(anchor="w", padx=10)
        self.delay = ctk.CTkEntry(global_frame, width=120)
        self.delay.pack(anchor="w", padx=10, pady=2)

        ctk.CTkLabel(global_frame, text="Telegram Bot Token").pack(anchor="w", padx=10)
        self.tg_token = ctk.CTkEntry(global_frame, width=300)
        self.tg_token.pack(anchor="w", padx=10, pady=2)
        ctk.CTkLabel(global_frame, text="Telegram Chat ID").pack(anchor="w", padx=10)
        self.tg_chat = ctk.CTkEntry(global_frame, width=300)
        self.tg_chat.pack(anchor="w", padx=10, pady=2)

        # Sincronizzazione
        self.sync_mode_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(global_frame, text="Abilita sincronizzazione oraria (es. 0,5,10...)", variable=self.sync_mode_var).pack(anchor="w", padx=10, pady=2)
        ctk.CTkLabel(global_frame, text="Intervallo di sincronizzazione (minuti)").pack(anchor="w", padx=10)
        self.sync_interval = ctk.CTkEntry(global_frame, width=120)
        self.sync_interval.insert(0, "5")
        self.sync_interval.pack(anchor="w", padx=10, pady=2)

        ctk.CTkButton(global_frame, text="💾 Salva impostazioni globali", command=self.save_global_settings).pack(pady=10)

        footer_left = ctk.CTkLabel(settings_scroll, text="© 2019-2026 • IBRA TECH", font=("Arial", 9))
        footer_left.pack(pady=(15,5))

        # RIGHT PANEL - LOG
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)
        log_frame = ctk.CTkFrame(right_frame)
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_frame, text="LOG", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(5,0))
        self.log_text = ctk.CTkTextbox(log_frame)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        self.update_counters()

    def refresh_checkbox_list(self):
        for widget in self.account_checkbox_frame.winfo_children():
            widget.destroy()
        self.account_checkboxes.clear()
        for acc in self.config.get("accounts", []):
            name = acc.get("name", "Senza nome")
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(self.account_checkbox_frame, text=name, variable=var)
            cb.pack(anchor="w", padx=10, pady=2)
            self.account_checkboxes[name] = var

    def add_account(self):
        self.open_account_editor()

    def edit_account(self):
        selected = [name for name, var in self.account_checkboxes.items() if var.get()]
        if not selected:
            msgbox.showerror("Errore", "Seleziona un account da modificare")
            return
        if len(selected) > 1:
            msgbox.showwarning("Attenzione", "Modifico solo il primo account selezionato")
        acc = next((a for a in self.config["accounts"] if a.get("name") == selected[0]), None)
        if acc:
            self.open_account_editor(acc)

    def delete_account(self):
        selected = [name for name, var in self.account_checkboxes.items() if var.get()]
        if not selected:
            msgbox.showerror("Errore", "Seleziona almeno un account")
            return
        for name in selected:
            self.config["accounts"] = [a for a in self.config["accounts"] if a.get("name") != name]
        save_config(self.config)
        self.refresh_checkbox_list()
        # Ricostruisci tabella contatori
        self.table_labels.clear()
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        headers = ["Account", "Email", "Sessione", "Giorno"]
        for col, txt in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=txt, font=("Arial", 11, "bold"))
            lbl.grid(row=0, column=col, padx=5, pady=2, sticky="ew")
        for row, acc in enumerate(self.config.get("accounts", []), start=1):
            name = acc.get("name", "")
            email = acc.get("email", "")
            self.table_labels[name] = {}
            ctk.CTkLabel(self.table_frame, text=name).grid(row=row, column=0, padx=5, pady=2)
            ctk.CTkLabel(self.table_frame, text=email).grid(row=row, column=1, padx=5, pady=2)
            self.table_labels[name]["session"] = ctk.CTkLabel(self.table_frame, text="0/28")
            self.table_labels[name]["session"].grid(row=row, column=2, padx=5, pady=2)
            self.table_labels[name]["daily"] = ctk.CTkLabel(self.table_frame, text="0/70")
            self.table_labels[name]["daily"].grid(row=row, column=3, padx=5, pady=2)
        for col in range(4):
            self.table_frame.grid_columnconfigure(col, weight=1)
        self.update_counters()
        self._log(f"Eliminati account: {', '.join(selected)}")

    def open_account_editor(self, account=None):
        editor = ctk.CTkToplevel(self)
        editor.title("Modifica Account")
        editor.geometry("750x700")
        editor.grab_set()
        editor.transient(self)
        editor.focus_force()
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
            ("proxy", "Proxy specifico (host:port:user:pass) - opzionale"),
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
                        "persons", "proxy"]:
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
            self.refresh_checkbox_list()
            # Aggiorna tabella contatori
            self.table_labels.clear()
            for widget in self.table_frame.winfo_children():
                widget.destroy()
            headers = ["Account", "Email", "Sessione", "Giorno"]
            for col, txt in enumerate(headers):
                lbl = ctk.CTkLabel(self.table_frame, text=txt, font=("Arial", 11, "bold"))
                lbl.grid(row=0, column=col, padx=5, pady=2, sticky="ew")
            for row2, acc2 in enumerate(self.config.get("accounts", []), start=1):
                name2 = acc2.get("name", "")
                email2 = acc2.get("email", "")
                self.table_labels[name2] = {}
                ctk.CTkLabel(self.table_frame, text=name2).grid(row=row2, column=0, padx=5, pady=2)
                ctk.CTkLabel(self.table_frame, text=email2).grid(row=row2, column=1, padx=5, pady=2)
                self.table_labels[name2]["session"] = ctk.CTkLabel(self.table_frame, text="0/28")
                self.table_labels[name2]["session"].grid(row=row2, column=2, padx=5, pady=2)
                self.table_labels[name2]["daily"] = ctk.CTkLabel(self.table_frame, text="0/70")
                self.table_labels[name2]["daily"].grid(row=row2, column=3, padx=5, pady=2)
            for col in range(4):
                self.table_frame.grid_columnconfigure(col, weight=1)
            self.update_counters()
            editor.destroy()

        ctk.CTkButton(scroll_frame, text="💾 Salva", command=save).grid(row=row, column=0, columnspan=2, pady=20)

    def save_global_settings(self):
        self.config["settings"]["check_interval_sec"] = int(self.interval.get())
        self.config["settings"]["request_delay_sec"] = int(self.delay.get())
        self.config["settings"]["telegram_bot_token"] = self.tg_token.get()
        self.config["settings"]["telegram_chat_id"] = self.tg_chat.get()
        self.config["settings"]["sync_mode"] = self.sync_mode_var.get()
        self.config["settings"]["sync_interval"] = int(self.sync_interval.get())
        save_config(self.config)
        msgbox.showinfo("Info", "Impostazioni globali salvate")

    def save_global_proxy(self):
        host = self.proxy_host.get().strip()
        port = self.proxy_port.get().strip()
        user = self.proxy_user.get().strip()
        pwd = self.proxy_pass.get().strip()
        if host and port:
            proxy_str = f"{host}:{port}"
            if user and pwd:
                proxy_str += f":{user}:{pwd}"
            self.config["settings"]["proxy_list"] = [proxy_str]
        else:
            self.config["settings"]["proxy_list"] = []
        self.config["settings"]["proxy_enabled"] = bool(host and port)
        save_config(self.config)
        msgbox.showinfo("Info", "Proxy globale salvato")

    def _load_settings_into_ui(self):
        settings = self.config["settings"]
        self.interval.insert(0, str(settings.get("check_interval_sec", DEFAULT_CHECK_INTERVAL_SEC)))
        self.delay.insert(0, str(settings.get("request_delay_sec", REQUEST_DELAY_SECONDS)))
        self.tg_token.insert(0, settings.get("telegram_bot_token", ""))
        self.tg_chat.insert(0, settings.get("telegram_chat_id", ""))
        self.sync_mode_var.set(settings.get("sync_mode", False))
        self.sync_interval.insert(0, str(settings.get("sync_interval", 5)))
        proxy_list = settings.get("proxy_list", [])
        if proxy_list:
            first_proxy = proxy_list[0]
            parts = first_proxy.split(':')
            if len(parts) >= 2:
                self.proxy_host.insert(0, parts[0])
                self.proxy_port.insert(0, parts[1])
                if len(parts) >= 4:
                    self.proxy_user.insert(0, parts[2])
                    self.proxy_pass.insert(0, parts[3])

    def start_selected(self):
        selected = [name for name, var in self.account_checkboxes.items() if var.get()]
        if not selected:
            msgbox.showerror("Errore", "Seleziona almeno un account")
            return
        for name in selected:
            if name in self.processes and self.processes[name].running:
                self._log(f"Monitoraggio già attivo per {name}")
                continue
            acc = next((a for a in self.config["accounts"] if a.get("name") == name), None)
            if not acc:
                continue
            settings = self.config["settings"].copy()
            settings["check_interval_sec"] = int(self.interval.get())
            settings["request_delay_sec"] = int(self.delay.get())
            settings["telegram_bot_token"] = self.tg_token.get()
            settings["telegram_chat_id"] = self.tg_chat.get()
            settings["sync_mode"] = self.sync_mode_var.get()
            settings["sync_interval"] = int(self.sync_interval.get())
            proc = BotProcess(acc, settings, self._log)
            proc.start()
            self.processes[name] = proc

    def stop_selected(self):
        selected = [name for name, var in self.account_checkboxes.items() if var.get()]
        if not selected:
            msgbox.showerror("Errore", "Seleziona almeno un account")
            return
        for name in selected:
            if name in self.processes:
                self.processes[name].stop()
                del self.processes[name]
                self._log(f"Fermato monitoraggio per {name}")

    def stop_all(self):
        for name, proc in list(self.processes.items()):
            proc.stop()
            del self.processes[name]
        self._log("Fermati tutti i monitoraggi")

if __name__ == "__main__":
    app = App()
    app.mainloop()