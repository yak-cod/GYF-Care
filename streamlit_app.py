# streamlit_app.py - VERSIÓN SIMPLIFICADA Y MODERNA
import streamlit as st

# Importar los módulos refactorizados
from presentation import ui_routes, ui_graphs_optimized

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
    .sidebar-stat {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sidebar-stat h3 {
        margin: 0;
        font-size: 1.8rem;
    }
    .sidebar-stat p {
        margin: 0;
        font-size: 0.9rem;
        opacity: 0.9;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ================================
# HEADER
# ================================
st.markdown('<div class="main-title">GYF-Care</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Sistema de Asignación Hospitalaria</div>',
    unsafe_allow_html=True,
)

# ================================
# SIDEBAR - NAVEGACIÓN
# ================================
with st.sidebar:
    st.image(
        "https://w7.pngwing.com/pngs/870/305/png-transparent-peru-flag-thumbnail.png",
        width=60,
    )
    
    st.markdown("### Navegación")
    
    menu = st.radio(
        "Selecciona un módulo:",
        [
            "Asignación de Pacientes",
            "Visualización de Red",
        ],
        label_visibility="collapsed",
    )
    
    st.divider()
    
    # Estadísticas del sistema
    st.markdown("### Estado del Sistema")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            <div class="sidebar-stat">
                <h3>1,400</h3>
                <p>Pacientes</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col2:
        st.markdown(
            """
            <div class="sidebar-stat">
                <h3>28</h3>
                <p>Hospitales</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    st.markdown(
        """
        <div style='text-align: center; padding: 0.5rem; background: #f0f2f6; border-radius: 8px; margin-top: 0.5rem;'>
            <small style='color: #666;'>Backend: <strong style='color: #10b981;'>Activo</strong></small><br>
            <small style='color: #666;'>Base de Datos: <strong>Azure MySQL</strong></small>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.divider()
    st.caption("© 2025 GYF-Care | TB2")

# ================================
# CONTENIDO PRINCIPAL
# ================================

if menu == "Asignación de Pacientes":
    ui_routes.show_routes_module()

elif menu == "Visualización de Red":
    ui_graphs_optimized.show_graphs_module()