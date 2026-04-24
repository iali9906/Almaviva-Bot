#!/usr/bin/env python3
"""
Modulo di autenticazione per Almaviva API.
Gestisce il login OAuth2 e il refresh del token.
"""
import requests
import time

AUTH_TOKEN_URL = "https://egyiam.almaviva-visa.it/realms/oauth2-visaSystem-realm-pkce/protocol/openid-connect/token"
CLIENT_ID = "aa-visasys-public"

def login(email, password, proxy_dict=None):
    """
    Esegue il login OAuth2 con grant_type=password.
    Restituisce il token_data (dict con access_token, refresh_token, expires_in, ecc.)
    """
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": email,
        "password": password
    }
    session = requests.Session()
    if proxy_dict:
        session.proxies.update(proxy_dict)
    
    resp = session.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 900)
    token_data["refresh_expires_at"] = time.time() + token_data.get("refresh_expires_in", 1200)
    return token_data

def refresh_token(refresh_token_value, proxy_dict=None):
    """
    Rinnova il token usando il refresh_token.
    """
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token_value
    }
    session = requests.Session()
    if proxy_dict:
        session.proxies.update(proxy_dict)
    
    resp = session.post(AUTH_TOKEN_URL, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 900)
    token_data["refresh_expires_at"] = time.time() + token_data.get("refresh_expires_in", 1200)
    return token_data