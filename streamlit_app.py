# streamlit_app.py
import streamlit as st
from infrastructure.data_loader import cargar_datos
from infrastructure.graph_builder import GraphBuilder
from application.assignment_service import AssignmentService
from presentation import ui_assignment, ui_graph, ui_map
from presentation.ui_backend_dashboard import show_backend_dashboard


st.set_page_config(
    page_title="GYF-Care",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado
st.markdown(
    """
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">GYF-Care - Gestión de Asignación de Pacientes</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">Sistema inteligente de asignación con UFDS y rutas reales</div>',
    unsafe_allow_html=True,
)

# ------------------------
# Cargar datos iniciales (desde CSV, para el front local)
# ------------------------
@st.cache_data
def load_initial_data():
    """Carga los datos iniciales y los cachea para mejor performance."""
    return cargar_datos("data/pacientesprueba.csv", "data/hospitalesprueba.csv")


if "pacientes_df" not in st.session_state or "hosp_state" not in st.session_state:
    with st.spinner("Cargando datos del sistema..."):
        pacientes_df, hosp_state = load_initial_data()
        st.session_state["pacientes_df"] = pacientes_df
        st.session_state["hosp_state"] = hosp_state

pacientes_df = st.session_state["pacientes_df"]
hosp_state = st.session_state["hosp_state"]

# ------------------------
# Inicializar servicios (si los usas en otras partes del proyecto)
# ------------------------
if "graph_builder" not in st.session_state:
    with st.spinner("Inicializando estructuras de grafos..."):
        # Usar los datos originales para construir los grafos
        _, hospitales_df_original = cargar_datos(
            "data/pacientesprueba.csv", "data/hospitalesprueba.csv"
        )
        st.session_state["graph_builder"] = GraphBuilder(hospitales_df_original)

if "assignment_service" not in st.session_state:
    with st.spinner("Inicializando servicio de asignación..."):
        _, hospitales_df_original = cargar_datos(
            "data/pacientesprueba.csv", "data/hospitalesprueba.csv"
        )
        st.session_state["assignment_service"] = AssignmentService(
            hospitales_df_original
        )

graph_builder = st.session_state["graph_builder"]
assignment_service = st.session_state["assignment_service"]

# ------------------------
# Barra lateral con información
# ------------------------
with st.sidebar:
    st.image(
        "https://w7.pngwing.com/pngs/870/305/png-transparent-peru-flag-thumbnail.png",
        width=80,
    )
    st.markdown("### Estado del Sistema")

    # Métricas generales
    total_pacientes = len(pacientes_df)
    total_hospitales = len(hosp_state)
    camas_disponibles = int(hosp_state["Capacidad_Camas"].sum())

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Pacientes", total_pacientes)
        st.metric("Hospitales", total_hospitales)
    with col2:
        st.metric("Camas", camas_disponibles)
        departamentos = (
            hosp_state["Departamento"].nunique()
            if "Departamento" in hosp_state.columns
            else 0
        )
        st.metric("Departamentos", departamentos)

    st.divider()

    # Menú de navegación
    st.markdown("### Navegación")
    menu = st.radio(
        "Selecciona una vista:",
        [
            "Mapa Interactivo",
            "Visualización de Grafos",
            "Asignaciones",
            "Algoritmos y Grafos (Backend)",  # 👈 NUEVA PESTAÑA
        ],
        label_visibility="collapsed",
    )

    st.divider()

# ------------------------
# Contenido principal según menú
# ------------------------
if menu == "Mapa Interactivo":
    ui_map.show_map(pacientes_df, hosp_state)

elif menu == "Visualización de Grafos":
    # Nueva visualización interactiva usando los DataFrames reales
    ui_graph.show_graph(
        pacientes_df,
        hosp_state,
    )

elif menu == "Asignaciones":
    ui_assignment.show_assignment(pacientes_df, hosp_state)

elif menu == "Algoritmos y Grafos (Backend)":
    # Panel que consume tu backend Flask vía /api/*
    show_backend_dashboard()

# ------------------------
# Footer
# ------------------------
st.divider()
st.markdown(
    """
<div style="text-align: center; color: #888; padding: 1rem;">
    <small>GYF-Care v1.0 | Gestión Inteligente de Asignación Hospitalaria | 2025</small>
</div>
""",
    unsafe_allow_html=True,
)
