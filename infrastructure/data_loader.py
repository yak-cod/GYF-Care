from typing import Tuple
import pandas as pd
import streamlit as st

# cambiar a en streamlit_app.py "data/hospitalesprueba.csv" de prueba para tener una muestra mas pequeña y sea más real el resultado
@st.cache_data 
def cargar_datos(pacientes_path, hospitales_path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga pacientes y hospitales desde CSV. Normaliza nombres de columnas.
    Retorna (pacientes_df, hospitales_df).
    """
    pacientes = pd.read_csv(pacientes_path)
    hospitales = pd.read_csv(hospitales_path)

    # Normalizar columnas (eliminar espacios alrededor)
    pacientes.columns = [c.strip() for c in pacientes.columns]
    hospitales.columns = [c.strip() for c in hospitales.columns]

    # Asegurar columnas numéricas tengan tipo correcto si es posible
    if "Latitud" in pacientes.columns:
        pacientes["Latitud"] = pd.to_numeric(pacientes["Latitud"], errors="coerce")
    if "Longitud" in pacientes.columns:
        pacientes["Longitud"] = pd.to_numeric(pacientes["Longitud"], errors="coerce")

    if "Latitud" in hospitales.columns:
        hospitales["Latitud"] = pd.to_numeric(hospitales["Latitud"], errors="coerce")
    if "Longitud" in hospitales.columns:
        hospitales["Longitud"] = pd.to_numeric(hospitales["Longitud"], errors="coerce")

    return pacientes, hospitales
