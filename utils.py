import time
from datetime import datetime

def log_message(log_callback, msg):
    if log_callback:
        log_callback(msg)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def wait_seconds(sec):
    time.sleep(sec)

def parse_iso_slot(iso_string):
    try:
        date_part = iso_string.split('T')[0]
        time_part = iso_string.split('T')[1].split('+')[0][:5]
        return date_part, time_part
    except:
        return None, None