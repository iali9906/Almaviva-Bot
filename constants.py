# Tipi di visto (nome -> id)
VISA_TYPES = {
    "Employment (record number 2026)": 32,
    "Employment (record number 2025)": 31,
    "Tourism Visa": 1,
    "Business Visa": 5,
    "Sport Visa": 10,
    "Study Visa (C)": 9,
    "Study Visa (D)": 8,
    "Medical Visa": 15,
    "Family Reunion": 19,
    "Family Reunion Visa for children": 20,
    "Re-entry Visa (D)": 4,
}

# Uffici
OFFICES = {"Cairo": 1, "Alessandria": 2}

# Endpoint API
BASE_URL = "https://egyapi.almaviva-visa.it"
AUTH_TOKEN_URL = "https://egyiam.almaviva-visa.it/realms/oauth2-visaSystem-realm-pkce/protocol/openid-connect/token"
CHECKS_URL = "https://egyapi.almaviva-visa.it/reservation-manager/api/planning/v1/checks"
FREE_SLOTS_URL = "https://egyapi.almaviva-visa.it/reservation-manager/api/slots/v1/free"

# Parametri client per il login OAuth2
CLIENT_ID = "aa-visasys-public"

# Limiti e temporizzazioni
DEFAULT_CHECK_INTERVAL_MIN = 5
REQUEST_DELAY_SECONDS = 30
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 60

# Orario di ufficio (disabilitato nel codice)
OFFICE_HOURS_START = 9
OFFICE_HOURS_END = 16