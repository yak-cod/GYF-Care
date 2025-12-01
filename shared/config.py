# shared/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# CONFIGURACIÓN GENERAL
# ============================================
APP_TITLE = "GYF Care — Asignación inteligente de pacientes"
CENTER_COORDS = [-12.0464, -77.0428]  # Lima centro
DEFAULT_TOP_K = 5
MAP_WIDTH = 1100
MAP_HEIGHT = 650

# ============================================
# BACKEND API
# ============================================
# Detectar si estamos en Streamlit Cloud o local
try:
    import streamlit as st
    # En Streamlit Cloud o local con secrets
    BACKEND_URL = st.secrets.get("backend", {}).get("base_url", "https://gyf-care-backend.onrender.com")
except:
    # Fallback: usar .env o hardcoded
    BACKEND_URL = os.getenv("BACKEND_URL", "https://gyf-care-backend.onrender.com")

# ============================================
# OPENROUTESERVICE API
# ============================================
try:
    import streamlit as st
    # En Streamlit Cloud
    ORS_API_KEY = st.secrets.get("ors", {}).get("api_key", "")
    ORS_BASE_URL = st.secrets.get("ors", {}).get("base_url", "https://api.openrouteservice.org")
    ORS_TIMEOUT = st.secrets.get("ors", {}).get("timeout", 10)
    ORS_MAX_RETRIES = st.secrets.get("ors", {}).get("max_retries", 3)
except:
    # En local
    ORS_API_KEY = os.getenv(
        "ORS_API_KEY",
        "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjdjNDczMzkwZmIzNDQxMGZiNWFiNWE5YjcyMTg1MjI2IiwiaCI6Im11cm11cjY0In0="
    )
    ORS_BASE_URL = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org")
    ORS_TIMEOUT = int(os.getenv("ORS_TIMEOUT", "10"))
    ORS_MAX_RETRIES = int(os.getenv("ORS_MAX_RETRIES", "3"))

ORS_DIRECTIONS_ENDPOINT = f"{ORS_BASE_URL}/v2/directions/driving-car"

# ============================================
# DEPARTAMENTOS (Coordenadas de centros)
# ============================================
DEPARTAMENTO_COORDS = {
    "Amazonas": [-5.7667, -77.8667],
    "Áncash": [-9.5333, -77.5167],
    "Apurímac": [-13.6333, -73.3667],
    "Arequipa": [-16.4090, -71.5375],
    "Ayacucho": [-13.1667, -74.2167],
    "Cajamarca": [-7.1500, -78.5167],
    "Cusco": [-13.5167, -71.9833],
    "Huancavelica": [-12.7833, -74.9833],
    "Huánuco": [-9.9333, -76.2333],
    "Junín": [-12.0667, -75.2000],
    "La Libertad": [-8.1167, -79.0333],
    "Lima": [-12.0464, -77.0428],
    "Pasco": [-10.6833, -76.2667],
    "Puno": [-15.8333, -70.0333],
    "San Martín": [-6.4833, -76.3667],
    "Tacna": [-18.0167, -70.2500],
    "Moquegua": [-17.1833, -70.9333],
}

# ============================================
# CACHÉ DE RUTAS
# ============================================
CACHE_DIR = "cache"
ENABLE_ROUTE_CACHE = True