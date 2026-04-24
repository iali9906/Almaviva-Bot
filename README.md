# 🚀 Almaviva Bot Pro

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

### Automatizza. Scala. Prenota prima degli altri.



\

---

## ⚡ Cos'è Almaviva Bot Pro

**Almaviva Bot Pro** è un bot avanzato progettato per **monitorare e prenotare appuntamenti automaticamente**, riducendo drasticamente tempi di attesa e intervento manuale.

Pensato per chi ha bisogno di:

* velocità
* affidabilità
* scalabilità

Non è un semplice script: è una **soluzione completa e pronta all’uso**.

---

## 💼 Perché sceglierlo

* 🧠 **Automazione intelligente** → controlla e prenota senza intervento umano
* ⚡ **Velocità superiore** → reagisce in tempo reale alla disponibilità
* 🔁 **Scalabilità reale** → gestisci più account contemporaneamente
* 🌐 **Anonimato e stabilità** → proxy + rotazione IP integrata
* 🔔 **Controllo totale** → notifiche istantanee su Telegram

---

## ✨ Funzionalità Premium

* 👥 **Multi-account management**
* 🌐 Supporto completo a **proxy (Smartproxy, BrightData, ecc.)**
* 🔄 **Rotazione IP automatica**
* 🛡️ Sistema avanzato **anti-429 / rate limit bypass**
* 📲 **Notifiche Telegram in tempo reale**
* 🖥️ Interfaccia **GUI intuitiva**
* ⚙️ Modalità **headless**
* 🧩 Architettura **modulare ed estendibile**

---
## 📁 Struttura del progetto
Almaviva-Bot/
├── main.py # GUI principale
├── bot_cli.py # CLI per test rapidi
├── api_client.py # Client API
├── auth.py # Login e refresh token
├── config.py # Gestione configurazione
├── constants.py # Costanti e endpoint
├── proxy_manager.py # Gestione proxy
├── notifier.py # Notifiche Telegram
├── utils.py # Utility
├── requirements.txt # Dipendenze
├── README.md # Documentazione
└── .gitignore # File esclusi
---

## 🖥️ Compatibilità

✔ Windows
✔ macOS
✔ Linux

---

## 🚀 Avvio rapido

```bash
git clone https://github.com/iali9906/Almaviva-BOT.git
cd Almaviva-BOT
python -m venv venv
source venv/bin/activate  # oppure venv\Scripts\activate su Windows
pip install -r requirements.txt
python main.py
```

---

## ⚙️ Setup in pochi minuti

Configura facilmente:

* 👤 **Account multipli**
* 🌐 **Proxy provider**
* 📲 **Telegram (BOT_TOKEN + CHAT_ID)**
* 🔧 Parametri di esecuzione (intervalli, headless, retry)

---

## 📈 Evoluzione del progetto

Il bot è stato sviluppato in modo progressivo per garantire stabilità e performance crescenti:

| Commit | Versione   | Descrizione                                     |
| ------ | ---------- | ----------------------------------------------- |
| 1      | v0.1.0     | Prima versione con login via browser (Selenium) |
| 2      | v0.2.0     | Aggiunto supporto proxy rotanti                 |
| 3      | v0.3.0     | Introdotto `bot_cli.py` e login diretto via API |
| 4      | v0.4.0     | Refresh token automatico + gestione errori 429  |
| 5      | v0.5.0     | Supporto multi-account e rotazione account      |
| 6      | **v1.0.0** | 🎯 Prima release stabile                        |

---

## 🧪 Roadmap

* [ ] Risoluzione CAPTCHA avanzata
* [ ] Dashboard web
* [ ] Sistema plugin
* [ ] Analytics e logging avanzato

---

## ⚠️ Disclaimer

Questo software è fornito a scopo educativo e tecnico.
L'utente è responsabile dell’utilizzo conforme ai termini del servizio della piattaforma Almaviva.

---

## 📄 Licenza

Licenza **MIT**.

---

## 📁 `.gitignore`

```gitignore
__pycache__/
*.pyc
almaviva_config.json
token_cache.json
.env
venv/
```
## 👨‍💻 Autore

Ibrahim Ali