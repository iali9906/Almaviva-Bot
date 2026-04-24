import requests

def send_telegram(bot_token, chat_id, message, log_callback=None):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=5)
        if log_callback:
            log_callback(f"Telegram inviato (status {resp.status_code})")
        return resp.status_code == 200
    except Exception as e:
        if log_callback:
            log_callback(f"Errore Telegram: {e}")
        return False