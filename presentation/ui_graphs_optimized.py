# presentation/ui_graphs_optimized.py - VERSIÓN SIMPLIFICADA
import streamlit as st
import requests
import streamlit.components.v1 as components
from pyvis.network import Network
import folium
from streamlit_folium import st_folium

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
    
    for node in nodes:
        color = "#FF6B6B" if node["type"] == "patient" else "#4ECDC4"
        net.add_node(
            node["id"],
            label=node["id"],
            color=color,
            title=f"Tipo: {node['type']}<br>Lat: {node['lat']:.4f}<br>Lon: {node['lon']:.4f}",
            size=15
        )
    
    for edge in edges:
        net.add_edge(
            edge["from"],
            edge["to"],
            value=edge["weight"],
            title=f"Distancia: {edge['weight']:.2f} km"
        )
    
    return net


def create_map_visualization(nodes, edges):
    """Crea un mapa con Folium mostrando el grafo sobre coordenadas reales."""
    
    nodes_dict = {node["id"]: node for node in nodes}
    
    if nodes:
        center_lat = sum(n["lat"] for n in nodes) / len(nodes)
        center_lon = sum(n["lon"] for n in nodes) / len(nodes)
    else:
        center_lat, center_lon = -9.19, -75.01
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="OpenStreetMap"
    )
    
    # Dibujar aristas
    for edge in edges:
        from_node = nodes_dict.get(edge["from"])
        to_node = nodes_dict.get(edge["to"])
        
        if from_node and to_node:
            if from_node["type"] == "patient" and to_node["type"] == "hospital":
                color = "#4ECDC4"
            elif from_node["type"] == "hospital" and to_node["type"] == "patient":
                color = "#4ECDC4"
            else:
                color = "#95a5a6"
            
            folium.PolyLine(
                locations=[
                    [from_node["lat"], from_node["lon"]],
                    [to_node["lat"], to_node["lon"]]
                ],
                color=color,
                weight=1,
                opacity=0.4,
                tooltip=f"{edge['from']} → {edge['to']}: {edge['weight']:.2f} km"
            ).add_to(m)
    
    # Dibujar nodos
    patients = [n for n in nodes if n["type"] == "patient"]
    hospitals = [n for n in nodes if n["type"] == "hospital"]
    
    for hospital in hospitals:
        folium.CircleMarker(
            location=[hospital["lat"], hospital["lon"]],
            radius=6,
            color="#2C3E50",
            fill=True,
            fillColor="#3498DB",
            fillOpacity=0.8,
            popup=f"<b>Hospital:</b> {hospital['id']}",
            tooltip=f"🏥 {hospital['id']}"
        ).add_to(m)
    
    for patient in patients:
        folium.CircleMarker(
            location=[patient["lat"], patient["lon"]],
            radius=4,
            color="#C0392B",
            fill=True,
            fillColor="#E74C3C",
            fillOpacity=0.8,
            popup=f"<b>Paciente:</b> {patient['id']}",
            tooltip=f"👤 {patient['id']}"
        ).add_to(m)
    
    return m


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_graphs_module():
    st.header("📊 Visualización de Grafo Bipartito")
    st.markdown("Explora la red de conexiones entre pacientes y hospitales utilizando el algoritmo de grafo bipartito.")
    
    st.sidebar.header("⚙️ Configuración del Grafo")
    
    # Solo grafo bipartito
    params = {}
    params["k"] = st.sidebar.slider("K (hospitales por paciente)", min_value=1, max_value=10, value=3, key="bipartite_k")
    params["limit"] = st.sidebar.slider("Límite de pacientes", min_value=20, max_value=500, value=100, step=20, key="bipartite_limit")
    
    department = st.sidebar.text_input("Filtrar por departamento (opcional):", "", key="bipartite_dept")
    if department:
        params["department"] = department
    
    if st.sidebar.button("🔄 Generar Grafo Bipartito", type="primary", use_container_width=True, key="generate_bipartite"):
        with st.spinner("Generando grafo bipartito..."):
            graph_data = fetch_graph("bipartite", **params)
        
        if graph_data:
            st.session_state["current_graph"] = graph_data
            st.session_state["graph_params"] = params
            st.rerun()
    
    if "current_graph" in st.session_state:
        graph_data = st.session_state["current_graph"]
        
        st.subheader("📈 Métricas del Grafo")
        
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        patients = [n for n in nodes if n.get("type") == "patient"]
        hospitals = [n for n in nodes if n.get("type") == "hospital"]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Pacientes", len(patients))
        col2.metric("Hospitales", len(hospitals))
        col3.metric("Conexiones", len(edges))
        
        total_nodes = len(patients) + len(hospitals)
        if total_nodes > 0:
            density = len(edges) / total_nodes
            col4.metric("Densidad", f"{density:.2f}")
        else:
            col4.metric("Densidad", "N/A")
        
        st.info(f"**Algoritmo:** Grafo Bipartito KNN | **Complejidad:** {graph_data.get('big_o', 'N/A')} | **Tiempo:** {graph_data.get('time_ms', 0):.2f} ms")
        
        st.markdown("""
        ### 💡 ¿Qué es un Grafo Bipartito?
        
        Un **grafo bipartito** es una estructura donde los nodos se dividen en dos conjuntos disjuntos:
        - 🔴 **Pacientes**: Solo se conectan con hospitales
        - 🔵 **Hospitales**: Solo reciben conexiones de pacientes
        
        **No existen conexiones** paciente-paciente ni hospital-hospital. Cada paciente se conecta a los **K hospitales más cercanos**.
        """)
        
        st.subheader("🎨 Visualización Interactiva (Grafo Abstracto)")
        
        if len(nodes) > 0:
            net = create_pyvis_network(nodes, edges)
            html_file = "temp_graph.html"
            net.save_graph(html_file)
            
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            components.html(html_content, height=650, scrolling=True)
            
            st.divider()
            st.subheader("🗺️ Visualización sobre Mapa Real")
            
            with st.spinner("🗺️ Generando mapa..."):
                map_viz = create_map_visualization(nodes, edges)
            
            st_folium(map_viz, width=1100, height=650, key="bipartite_map")
    
    else:
        st.info("👈 Configura los parámetros en el panel izquierdo y presiona **Generar Grafo Bipartito**")