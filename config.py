import json
import os

CONFIG_FILE = "almaviva_config.json"

DEFAULT_CONFIG = {
    "accounts": [],
    "settings": {
        "check_interval_min": 5,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "headless": False
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)