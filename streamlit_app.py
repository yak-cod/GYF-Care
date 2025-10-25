# streamlit_app.py
import streamlit as st
from infrastructure.data_loader import cargar_datos
from presentation import ui_assignment, ui_graph, ui_map

st.set_page_config(page_title="GYF-Care", layout="wide")
st.title("🏥 GYF-Care - Gestión de Asignación de Pacientes")

# ------------------------
# Cargar datos iniciales
# ------------------------
if "pacientes_df" not in st.session_state or "hosp_state" not in st.session_state:
    pacientes_df, hosp_state = cargar_datos("data/pacientesprueba.csv", "data/hospitalesprueba.csv")
    st.session_state["pacientes_df"] = pacientes_df
    st.session_state["hosp_state"] = hosp_state

pacientes_df = st.session_state["pacientes_df"]
hosp_state = st.session_state["hosp_state"]

# ------------------------
# Barra lateral
# ------------------------
menu = st.sidebar.radio("Navegación", ["Asignaciones", "Gráficos", "Mapa"])

if menu == "Asignaciones":
    ui_assignment.show_assignment(pacientes_df, hosp_state)
elif menu == "Gráficos":
    ui_graph.show_graph(pacientes_df, hosp_state)
elif menu == "Mapa":
    ui_map.show_map(pacientes_df, hosp_state)

