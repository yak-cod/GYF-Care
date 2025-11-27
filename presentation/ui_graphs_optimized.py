# presentation/ui_graphs_optimized.py - CON SIMULACIONES AVANZADAS
import streamlit as st
import requests
import streamlit.components.v1 as components
from pyvis.network import Network
import folium
from streamlit_folium import st_folium
import pandas as pd
import time
import random

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


def create_map_visualization(nodes, edges, highlight_removed=None):
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
        # Resaltar hospital eliminado
        if highlight_removed and hospital["id"] == highlight_removed:
            folium.CircleMarker(
                location=[hospital["lat"], hospital["lon"]],
                radius=8,
                color="#E74C3C",
                fill=True,
                fillColor="#E74C3C",
                fillOpacity=0.8,
                popup=f"<b>❌ ELIMINADO:</b> {hospital['id']}",
                tooltip=f"❌ {hospital['id']} (ELIMINADO)"
            ).add_to(m)
        else:
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


def remove_hospital_from_graph(graph_data, hospital_id):
    """Elimina un hospital del grafo y recalcula métricas."""
    nodes = [n for n in graph_data["nodes"] if n["id"] != hospital_id]
    
    # Filtrar aristas que involucran el hospital eliminado
    edges = [
        e for e in graph_data["edges"] 
        if e["from"] != hospital_id and e["to"] != hospital_id
    ]
    
    return {
        **graph_data,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_graphs_module():
    st.header("📊 Módulo 2: Visualización de Grafos")
    st.markdown("Explora diferentes representaciones de grafos de la red de pacientes y hospitales.")
    
    # TABS PRINCIPALES
    tabs = st.tabs([
        "🎨 Visualización Básica",
        "📊 Comparación de Grafos",
        "🎯 Simulación de Fallas",
        "🚑 Simulador en Vivo"
    ])
    
    # ================================
    # TAB 1: VISUALIZACIÓN BÁSICA
    # ================================
    with tabs[0]:
        st.sidebar.header("⚙️ Configuración del Grafo")
        
        graph_type = st.sidebar.selectbox(
            "Tipo de grafo:",
            ["knn", "radius", "bipartite"],
            format_func=lambda x: {
                "knn": "KNN (K-vecinos más cercanos)",
                "radius": "Radio (ε-vecindario)",
                "bipartite": "Bipartito (paciente→hospital)"
            }[x],
            key="basic_graph_type"
        )
        
        params = {}
        
        if graph_type == "knn":
            params["k"] = st.sidebar.slider("K (vecinos)", min_value=1, max_value=20, value=5, key="basic_k")
            params["limit"] = st.sidebar.slider("Límite de nodos", min_value=50, max_value=500, value=200, step=50, key="basic_limit")
        
        elif graph_type == "radius":
            params["radius_km"] = st.sidebar.slider("Radio (km)", min_value=10.0, max_value=200.0, value=50.0, step=10.0, key="basic_radius")
            params["limit"] = st.sidebar.slider("Límite de nodos", min_value=50, max_value=500, value=200, step=50, key="basic_limit_r")
        
        elif graph_type == "bipartite":
            params["k"] = st.sidebar.slider("K (hospitales por paciente)", min_value=1, max_value=10, value=3, key="basic_k_bip")
            params["limit"] = st.sidebar.slider("Límite de pacientes", min_value=20, max_value=500, value=100, step=20, key="basic_limit_bip")
        
        department = st.sidebar.text_input("Filtrar por departamento (opcional):", "", key="basic_dept")
        if department:
            params["department"] = department
        
        if st.sidebar.button("🔄 Generar Grafo", type="primary", use_container_width=True, key="basic_generate"):
            with st.spinner(f"Generando grafo {graph_type.upper()}..."):
                graph_data = fetch_graph(graph_type, **params)
            
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
            col3.metric("Aristas", len(edges))
            
            total_nodes = len(patients) + len(hospitals)
            if total_nodes > 0:
                density = len(edges) / total_nodes
                col4.metric("Densidad", f"{density:.2f}")
            else:
                col4.metric("Densidad", "N/A")
            
            st.info(f"**Algoritmo:** {graph_data.get('algorithm', 'N/A')} | **Complejidad:** {graph_data.get('big_o', 'N/A')} | **Tiempo:** {graph_data.get('time_ms', 0):.2f} ms")
            
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
                
                st_folium(map_viz, width=1100, height=650, key="basic_map")
        
        else:
            st.info("👈 Configura los parámetros en el panel izquierdo y presiona **Generar Grafo**")
    
    # ================================
    # TAB 2: COMPARACIÓN DE GRAFOS
    # ================================
    with tabs[1]:
        st.subheader("📊 Comparación de Configuraciones de Grafo")
        st.markdown("Compara dos configuraciones diferentes lado a lado para entender el impacto de los parámetros.")
        
        col1, col2 = st.columns(2)
        
        # GRAFO A
        with col1:
            st.markdown("### 🔵 Grafo A")
            graph_type_a = st.selectbox(
                "Tipo:",
                ["knn", "radius", "bipartite"],
                key="compare_type_a"
            )
            
            params_a = {}
            if graph_type_a == "knn":
                params_a["k"] = st.slider("K:", 1, 20, 3, key="compare_k_a")
                params_a["limit"] = st.slider("Límite:", 50, 500, 150, 50, key="compare_limit_a")
            elif graph_type_a == "radius":
                params_a["radius_km"] = st.slider("Radio (km):", 10.0, 200.0, 30.0, 10.0, key="compare_radius_a")
                params_a["limit"] = st.slider("Límite:", 50, 500, 150, 50, key="compare_limit_ra")
            else:
                params_a["k"] = st.slider("K:", 1, 10, 2, key="compare_k_bip_a")
                params_a["limit"] = st.slider("Límite:", 20, 500, 100, 20, key="compare_limit_bip_a")
        
        # GRAFO B
        with col2:
            st.markdown("### 🟢 Grafo B")
            graph_type_b = st.selectbox(
                "Tipo:",
                ["knn", "radius", "bipartite"],
                key="compare_type_b"
            )
            
            params_b = {}
            if graph_type_b == "knn":
                params_b["k"] = st.slider("K:", 1, 20, 10, key="compare_k_b")
                params_b["limit"] = st.slider("Límite:", 50, 500, 150, 50, key="compare_limit_b")
            elif graph_type_b == "radius":
                params_b["radius_km"] = st.slider("Radio (km):", 10.0, 200.0, 100.0, 10.0, key="compare_radius_b")
                params_b["limit"] = st.slider("Límite:", 50, 500, 150, 50, key="compare_limit_rb")
            else:
                params_b["k"] = st.slider("K:", 1, 10, 5, key="compare_k_bip_b")
                params_b["limit"] = st.slider("Límite:", 20, 500, 100, 20, key="compare_limit_bip_b")
        
        if st.button("⚡ Generar Comparación", type="primary", use_container_width=True, key="compare_generate"):
            with st.spinner("Generando ambos grafos..."):
                graph_a = fetch_graph(graph_type_a, **params_a)
                graph_b = fetch_graph(graph_type_b, **params_b)
            
            if graph_a and graph_b:
                st.session_state["comparison_a"] = graph_a
                st.session_state["comparison_b"] = graph_b
                st.rerun()
        
        if "comparison_a" in st.session_state and "comparison_b" in st.session_state:
            graph_a = st.session_state["comparison_a"]
            graph_b = st.session_state["comparison_b"]
            
            st.success("✅ Comparación generada")
            
            # Métricas comparativas
            st.subheader("📊 Métricas Comparativas")
            
            comparison_data = {
                "Métrica": ["Nodos", "Aristas", "Densidad", "Tiempo (ms)"],
                "Grafo A": [
                    graph_a["total_nodes"],
                    graph_a["total_edges"],
                    f"{graph_a['total_edges'] / graph_a['total_nodes']:.2f}" if graph_a['total_nodes'] > 0 else "N/A",
                    f"{graph_a['time_ms']:.2f}"
                ],
                "Grafo B": [
                    graph_b["total_nodes"],
                    graph_b["total_edges"],
                    f"{graph_b['total_edges'] / graph_b['total_nodes']:.2f}" if graph_b['total_nodes'] > 0 else "N/A",
                    f"{graph_b['time_ms']:.2f}"
                ],
            }
            
            # Calcular diferencia porcentual
            diff_nodes = ((graph_b["total_nodes"] - graph_a["total_nodes"]) / graph_a["total_nodes"] * 100) if graph_a["total_nodes"] > 0 else 0
            diff_edges = ((graph_b["total_edges"] - graph_a["total_edges"]) / graph_a["total_edges"] * 100) if graph_a["total_edges"] > 0 else 0
            
            comparison_data["Diferencia"] = [
                f"{diff_nodes:+.1f}%",
                f"{diff_edges:+.1f}%",
                "-",
                "-"
            ]
            
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True)
            
            # Mapas lado a lado
            st.divider()
            st.subheader("🗺️ Visualización en Mapa")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🔵 Grafo A")
                map_a = create_map_visualization(graph_a["nodes"], graph_a["edges"])
                st_folium(map_a, width=500, height=500, key="map_compare_a")
            
            with col2:
                st.markdown("#### 🟢 Grafo B")
                map_b = create_map_visualization(graph_b["nodes"], graph_b["edges"])
                st_folium(map_b, width=500, height=500, key="map_compare_b")
    
    # ================================
    # TAB 3: SIMULACIÓN DE FALLAS
    # ================================
    with tabs[2]:
        st.subheader("🎯 Simulación de Fallas en la Red")
        st.markdown("Simula el colapso o cierre de un hospital y observa el impacto en la red.")
        
        if "current_graph" not in st.session_state:
            st.warning("⚠️ Primero genera un grafo en la pestaña 'Visualización Básica'")
        else:
            graph_data = st.session_state["current_graph"]
            nodes = graph_data.get("nodes", [])
            hospitals = [n for n in nodes if n.get("type") == "hospital"]
            
            if not hospitals:
                st.error("❌ El grafo actual no tiene hospitales")
            else:
                hospital_options = {h["id"]: h for h in hospitals}
                
                selected_hospital = st.selectbox(
                    "Selecciona el hospital a eliminar:",
                    list(hospital_options.keys()),
                    key="failure_hospital"
                )
                
                if st.button("🔥 Simular Falla del Hospital", type="primary", use_container_width=True, key="simulate_failure"):
                    with st.spinner(f"Eliminando {selected_hospital} y recalculando..."):
                        modified_graph = remove_hospital_from_graph(graph_data, selected_hospital)
                        st.session_state["failure_original"] = graph_data
                        st.session_state["failure_modified"] = modified_graph
                        st.session_state["failure_hospital"] = selected_hospital
                        st.rerun()
                
                if "failure_modified" in st.session_state:
                    original = st.session_state["failure_original"]
                    modified = st.session_state["failure_modified"]
                    removed_hosp = st.session_state["failure_hospital"]
                    
                    st.error(f"❌ Hospital eliminado: **{removed_hosp}**")
                    
                    # Análisis de impacto
                    st.subheader("📊 Análisis de Impacto")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "Hospitales",
                            modified["total_nodes"] - len([n for n in modified["nodes"] if n["type"] == "patient"]),
                            delta=-(original["total_nodes"] - modified["total_nodes"])
                        )
                    
                    with col2:
                        st.metric(
                            "Aristas",
                            modified["total_edges"],
                            delta=-(original["total_edges"] - modified["total_edges"])
                        )
                    
                    with col3:
                        # Pacientes potencialmente afectados
                        original_edges_with_hospital = len([e for e in original["edges"] if e["from"] == removed_hosp or e["to"] == removed_hosp])
                        st.metric(
                            "Conexiones perdidas",
                            original_edges_with_hospital,
                            delta=-original_edges_with_hospital,
                            delta_color="inverse"
                        )
                    
                    # Porcentaje de conectividad perdida
                    connectivity_loss = ((original["total_edges"] - modified["total_edges"]) / original["total_edges"] * 100) if original["total_edges"] > 0 else 0
                    
                    if connectivity_loss > 20:
                        st.error(f"🚨 **CRÍTICO:** Se perdió {connectivity_loss:.1f}% de la conectividad total")
                    elif connectivity_loss > 10:
                        st.warning(f"⚠️ **MODERADO:** Se perdió {connectivity_loss:.1f}% de la conectividad total")
                    else:
                        st.info(f"ℹ️ **LEVE:** Se perdió {connectivity_loss:.1f}% de la conectividad total")
                    
                    # Mapas antes/después
                    st.divider()
                    st.subheader("🗺️ Comparación Visual")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### ✅ ANTES (Red Original)")
                        map_before = create_map_visualization(original["nodes"], original["edges"])
                        st_folium(map_before, width=500, height=500, key="failure_before")
                    
                    with col2:
                        st.markdown(f"#### ❌ DESPUÉS (Sin {removed_hosp})")
                        map_after = create_map_visualization(modified["nodes"], modified["edges"], highlight_removed=removed_hosp)
                        st_folium(map_after, width=500, height=500, key="failure_after")
    
    # ================================
    # TAB 4: SIMULADOR EN VIVO
    # ================================
    with tabs[3]:
        st.subheader("🚑 Simulador de Asignación en Vivo")
        st.markdown("Simula la llegada de pacientes en tiempo real y su asignación a hospitales.")
        
        # Controles
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            simulation_speed = st.slider("Velocidad (pacientes/seg):", 1, 10, 3, key="sim_speed")
        
        with col2:
            max_patients = st.slider("Pacientes a generar:", 5, 50, 20, key="sim_max")
        
        with col3:
            if "simulation_running" not in st.session_state:
                st.session_state["simulation_running"] = False
            
            if st.button("▶️ Iniciar" if not st.session_state["simulation_running"] else "⏸️ Pausar", 
                        use_container_width=True, 
                        key="sim_toggle"):
                st.session_state["simulation_running"] = not st.session_state["simulation_running"]
                if st.session_state["simulation_running"]:
                    st.session_state["sim_patients_processed"] = 0
                    st.session_state["sim_assignments"] = []
                st.rerun()
        
        # Estado de simulación
        if "simulation_running" in st.session_state and st.session_state["simulation_running"]:
            st.info("🟢 Simulación en curso...")
            
            # Obtener hospitales disponibles
            try:
                response = requests.get(f"{BACKEND_URL}/hospitals", timeout=10)
                hospitals = response.json()["hospitals"]
                
                # Simular llegada de paciente
                if "sim_patients_processed" not in st.session_state:
                    st.session_state["sim_patients_processed"] = 0
                
                if st.session_state["sim_patients_processed"] < max_patients:
                    # Generar paciente aleatorio
                    random_hospital = random.choice(hospitals)
                    
                    # Crear "paciente" cerca de un hospital aleatorio
                    fake_patient = {
                        "id": f"SIM_{st.session_state['sim_patients_processed']:03d}",
                        "lat": random_hospital["lat"] + random.uniform(-0.5, 0.5),
                        "lon": random_hospital["lon"] + random.uniform(-0.5, 0.5),
                        "type": "patient"
                    }
                    
                    # Asignar al hospital más cercano (simplificado)
                    distances = []
                    for h in hospitals[:10]:  # Limitar a 10 para performance
                        dist = ((fake_patient["lat"] - h["lat"])**2 + (fake_patient["lon"] - h["lon"])**2)**0.5
                        distances.append((h, dist))
                    
                    distances.sort(key=lambda x: x[1])
                    assigned_hospital = distances[0][0]
                    
                    # Guardar asignación
                    if "sim_assignments" not in st.session_state:
                        st.session_state["sim_assignments"] = []
                    
                    st.session_state["sim_assignments"].append({
                        "patient": fake_patient,
                        "hospital": assigned_hospital,
                        "distance": distances[0][1] * 111  # Aproximar a km
                    })
                    
                    st.session_state["sim_patients_processed"] += 1
                    
                    # Esperar según velocidad
                    time.sleep(1.0 / simulation_speed)
                    st.rerun()
                else:
                    st.session_state["simulation_running"] = False
                    st.success(f"✅ Simulación completada: {max_patients} pacientes procesados")
            
            except Exception as e:
                st.error(f"Error en simulación: {e}")
                st.session_state["simulation_running"] = False
        
        # Mostrar resultados
        if "sim_assignments" in st.session_state and st.session_state["sim_assignments"]:
            assignments = st.session_state["sim_assignments"]
            
            st.divider()
            st.subheader("📊 Estadísticas de Simulación")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Pacientes procesados", len(assignments))
            col2.metric("Distancia promedio", f"{sum(a['distance'] for a in assignments) / len(assignments):.2f} km")
            
            # Contar hospitales únicos usados
            unique_hospitals = len(set(a["hospital"]["code"] for a in assignments))
            col3.metric("Hospitales utilizados", unique_hospitals)
            
            # Mapa de asignaciones
            st.subheader("🗺️ Mapa de Asignaciones en Vivo")
            
            m = folium.Map(location=[-9.19, -75.01], zoom_start=6)
            
            colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "darkblue", "cadetblue", "darkgreen"]
            
            for idx, assignment in enumerate(assignments[-20:]):  # Últimas 20
                patient = assignment["patient"]
                hospital = assignment["hospital"]
                color = colors[idx % len(colors)]
                
                # Paciente
                folium.CircleMarker(
                    location=[patient["lat"], patient["lon"]],
                    radius=4,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.6,
                    tooltip=patient["id"]
                ).add_to(m)
                
                # Hospital
                folium.CircleMarker(
                    location=[hospital["lat"], hospital["lon"]],
                    radius=6,
                    color="blue",
                    fill=True,
                    fillColor="lightblue",
                    fillOpacity=0.8,
                    tooltip=hospital["code"]
                ).add_to(m)
                
                # Línea de asignación
                folium.PolyLine(
                    locations=[[patient["lat"], patient["lon"]], [hospital["lat"], hospital["lon"]]],
                    color=color,
                    weight=2,
                    opacity=0.5
                ).add_to(m)
            
            st_folium(m, width=1100, height=600, key="simulation_map")
            
            # Tabla de asignaciones
            st.subheader("📋 Detalle de Asignaciones")
            summary = pd.DataFrame([{
                "Paciente": a["patient"]["id"],
                "Hospital": a["hospital"]["code"],
                "Distancia (km)": f"{a['distance']:.2f}"
            } for a in assignments[-20:]])
            
            st.dataframe(summary, use_container_width=True)