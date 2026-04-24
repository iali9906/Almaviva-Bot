import json
import os

CONFIG_FILE = "almaviva_config.json"

DEFAULT_CONFIG = {
    "accounts": [],
    "settings": {
        "check_interval_min": 5,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "proxy_enabled": False,
        "proxy_list": [],
        "proxy_host": "",
        "proxy_port": "",
        "proxy_username": "",
        "proxy_password": "",
        "headless": False
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        for acc in config.get("accounts", []):
            if "name" not in acc or not acc["name"]:
                acc["name"] = acc.get("email", "Account")
            if "proxy" not in acc:
                acc["proxy"] = ""
        return config
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)