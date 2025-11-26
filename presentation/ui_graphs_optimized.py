# presentation/ui_graphs_optimized.py - VERSIÓN CORREGIDA
import streamlit as st
import requests
import streamlit.components.v1 as components
from pyvis.network import Network

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:5000/api")

# ================================
# FUNCIONES AUXILIARES
# ================================

def fetch_graph(graph_type, **params):
    """Obtiene un grafo del backend."""
    try:
        response = requests.get(
            f"{BACKEND_URL}/graph/{graph_type}",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error al obtener grafo: {e}")
        return None


def create_pyvis_network(nodes, edges, height="600px"):
    """Crea una visualización interactiva con Pyvis."""
    net = Network(height=height, width="100%", bgcolor="#222222", font_color="white")
    
    # Configurar física para mejor layout
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      }
    }
    """)
    
    # Agregar nodos
    for node in nodes:
        color = "#FF6B6B" if node["type"] == "patient" else "#4ECDC4"
        net.add_node(
            node["id"],
            label=node["id"],
            color=color,
            title=f"Tipo: {node['type']}<br>Lat: {node['lat']:.4f}<br>Lon: {node['lon']:.4f}",
            size=15
        )
    
    # Agregar aristas
    for edge in edges:
        net.add_edge(
            edge["from"],
            edge["to"],
            value=edge["weight"],
            title=f"Distancia: {edge['weight']:.2f} km"
        )
    
    return net


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_graphs_module():
    st.header("📊 Módulo 2: Visualización de Grafos")
    st.markdown("Explora diferentes representaciones de grafos de la red de pacientes y hospitales.")
    
    # Configuración en sidebar
    st.sidebar.header("⚙️ Configuración del Grafo")
    
    graph_type = st.sidebar.selectbox(
        "Tipo de grafo:",
        ["knn", "radius", "bipartite"],
        format_func=lambda x: {
            "knn": "KNN (K-vecinos más cercanos)",
            "radius": "Radio (ε-vecindario)",
            "bipartite": "Bipartito (paciente→hospital)"
        }[x]
    )
    
    # Parámetros según el tipo de grafo
    params = {}
    
    if graph_type == "knn":
        params["k"] = st.sidebar.slider("K (vecinos)", min_value=1, max_value=20, value=5)
        params["limit"] = st.sidebar.slider("Límite de nodos", min_value=50, max_value=500, value=200, step=50)
    
    elif graph_type == "radius":
        params["radius_km"] = st.sidebar.slider("Radio (km)", min_value=10.0, max_value=200.0, value=50.0, step=10.0)
        params["limit"] = st.sidebar.slider("Límite de nodos", min_value=50, max_value=500, value=200, step=50)
    
    elif graph_type == "bipartite":
        params["k"] = st.sidebar.slider("K (hospitales por paciente)", min_value=1, max_value=10, value=3)
        params["limit"] = st.sidebar.slider("Límite de pacientes", min_value=20, max_value=500, value=100, step=20)
    
    # Filtro por departamento (opcional)
    department = st.sidebar.text_input("Filtrar por departamento (opcional):", "")
    if department:
        params["department"] = department
    
    # Botón para generar grafo
    if st.sidebar.button("🔄 Generar Grafo", type="primary", use_container_width=True):
        with st.spinner(f"Generando grafo {graph_type.upper()}..."):
            graph_data = fetch_graph(graph_type, **params)
        
        if graph_data:
            st.session_state["current_graph"] = graph_data
            st.session_state["graph_params"] = params
            st.rerun()
    
    # Mostrar grafo si existe en session_state
    if "current_graph" in st.session_state:
        graph_data = st.session_state["current_graph"]
        
        # Métricas del grafo
        st.subheader("📈 Métricas del Grafo")
        
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        # Contar pacientes y hospitales
        patients = [n for n in nodes if n.get("type") == "patient"]
        hospitals = [n for n in nodes if n.get("type") == "hospital"]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Pacientes", len(patients))
        col2.metric("Hospitales", len(hospitals))
        col3.metric("Aristas", len(edges))
        
        # Calcular densidad con seguridad
        total_nodes = len(patients) + len(hospitals)
        if total_nodes > 0:
            density = len(edges) / total_nodes
            col4.metric("Densidad", f"{density:.2f}")
        else:
            col4.metric("Densidad", "N/A")
        
        # Información adicional
        st.info(f"**Algoritmo:** {graph_data.get('algorithm', 'N/A')} | **Complejidad:** {graph_data.get('big_o', 'N/A')} | **Tiempo:** {graph_data.get('time_ms', 0):.2f} ms")
        
        # Visualización
        st.subheader("🎨 Visualización Interactiva")
        
        if len(nodes) == 0:
            st.warning("⚠️ El grafo no tiene nodos. Intenta con otros parámetros o departamento.")
        elif len(nodes) > 500:
            st.warning(f"⚠️ El grafo tiene {len(nodes)} nodos. Esto puede ser lento. Se recomienda usar menos de 500 nodos.")
        
        if len(nodes) > 0:
            # Crear visualización con Pyvis
            net = create_pyvis_network(nodes, edges)
            
            # Guardar HTML temporal
            html_file = "temp_graph.html"
            net.save_graph(html_file)
            
            # Leer y mostrar
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            components.html(html_content, height=650, scrolling=True)
            
            # Leyenda
            st.markdown("""
            **Leyenda:**
            - 🔴 Rojo: Pacientes
            - 🔵 Azul: Hospitales
            - 🔗 Líneas: Conexiones (grosor = distancia)
            
            **Interacción:**
            - Haz clic y arrastra para mover nodos
            - Rueda del mouse para zoom
            - Hover sobre nodos/aristas para ver detalles
            """)
    
    else:
        st.info("👈 Configura los parámetros en el panel izquierdo y presiona **Generar Grafo**")
    
    # Sección de comparación
    st.divider()
    st.subheader("🔬 Comparación de Algoritmos de Grafo")
    
    if st.button("⚡ Comparar 3 Algoritmos", use_container_width=True):
        with st.spinner("Ejecutando comparación..."):
            try:
                response = requests.get(
                    f"{BACKEND_URL}/graph/compare",
                    params={"limit": 200},
                    timeout=60
                )
                response.raise_for_status()
                comparison_data = response.json()
                
                st.success("✅ Comparación completada")
                
                # Mostrar resultados
                import pandas as pd
                
                results_df = pd.DataFrame(comparison_data["comparison"])
                
                st.dataframe(
                    results_df[["algorithm", "big_o", "time_ms", "nodes", "edges"]],
                    use_container_width=True
                )
                
                # Gráfico de tiempos
                import plotly.express as px
                
                fig = px.bar(
                    results_df,
                    x="algorithm",
                    y="time_ms",
                    color="algorithm",
                    title="Tiempo de Ejecución por Algoritmo",
                    labels={"time_ms": "Tiempo (ms)", "algorithm": "Algoritmo"}
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error en comparación: {e}")