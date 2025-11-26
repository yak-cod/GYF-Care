# streamlit_app.py - VERSIÓN REFACTORIZADA Y MODULAR
import streamlit as st

# Importar los módulos refactorizados
from presentation import ui_routes, ui_graphs_optimized, ui_algorithms

st.set_page_config(
    page_title="GYF-Care - Sistema de Asignación",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================
# ESTILO PERSONALIZADO
# ================================
st.markdown(
    """
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .module-header {
        background: linear-gradient(90deg, #1f77b4 0%, #54a0ff 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ================================
# HEADER
# ================================
st.markdown('<div class="main-title">🏥 GYF-Care</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Sistema Inteligente de Asignación de Pacientes con Algoritmos Avanzados</div>',
    unsafe_allow_html=True,
)

# ================================
# SIDEBAR - NAVEGACIÓN
# ================================
with st.sidebar:
    st.image(
        "https://w7.pngwing.com/pngs/870/305/png-transparent-peru-flag-thumbnail.png",
        width=80,
    )
    
    st.markdown("### 📱 Navegación")
    
    menu = st.radio(
        "Selecciona un módulo:",
        [
            "🗺️ Rutas Reales (OpenRouteService)",
            "🕸️ Visualización de Grafos",
            "⚙️ Comparación de Algoritmos",
        ],
        label_visibility="collapsed",
    )
    
    st.markdown("---")
    
    # Información del sistema
    st.markdown("### 📊 Información")
    st.info(
        """
        **Backend:** Conectado ✅  
        **Base de Datos:** Azure MySQL  
        **Pacientes:** ~1,400  
        **Hospitales:** ~28
        """
    )
    
    st.markdown("---")
    st.caption("© 2025 GYF-Care Team | TB2")

# ================================
# CONTENIDO PRINCIPAL
# ================================

if menu == "🗺️ Rutas Reales (OpenRouteService)":
    ui_routes.show_routes_module()

elif menu == "🕸️ Visualización de Grafos":
    ui_graphs_optimized.show_graphs_module()

elif menu == "⚙️ Comparación de Algoritmos":
    ui_algorithms.show_algorithms_module()