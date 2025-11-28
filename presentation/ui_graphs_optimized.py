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
    # TAB 4: SIMULADOR DE CONEXIÓN
    # ================================
    with tabs[3]:
        st.subheader("🎯 Simulador: Cómo se conecta un Paciente al Grafo")
        st.markdown("Visualiza paso a paso cómo un paciente se conecta a la red según el algoritmo seleccionado.")
        
        # Configuración del simulador
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Obtener lista de pacientes
            try:
                response = requests.get(f"{BACKEND_URL}/patients", params={"limit": 100}, timeout=10)
                patients_data = response.json()
                patients_list = patients_data.get("patients", [])
                
                if patients_list:
                    patient_options = {
                        f"{p['code']} - {p.get('disease', 'N/A')[:30]} ({p.get('department', 'N/A')})": p['code']
                        for p in patients_list
                    }
                    
                    selected_patient_label = st.selectbox(
                        "Selecciona un paciente:",
                        list(patient_options.keys()),
                        key="sim_patient_select"
                    )
                    selected_patient_code = patient_options[selected_patient_label]
                else:
                    st.error("No se pudieron cargar pacientes")
                    selected_patient_code = None
            except Exception as e:
                st.error(f"Error al cargar pacientes: {e}")
                selected_patient_code = None
        
        with col2:
            # Tipo de grafo para la simulación
            sim_graph_type = st.selectbox(
                "Tipo de grafo:",
                ["knn", "radius", "bipartite"],
                format_func=lambda x: {
                    "knn": "KNN",
                    "radius": "Radio",
                    "bipartite": "Bipartito"
                }[x],
                key="sim_graph_type"
            )
            
            # Parámetros según el tipo
            if sim_graph_type == "knn":
                sim_k = st.slider("K vecinos:", 1, 10, 5, key="sim_k")
                sim_params = {"k": sim_k, "limit": 200}
            elif sim_graph_type == "radius":
                sim_radius = st.slider("Radio (km):", 10.0, 150.0, 50.0, 10.0, key="sim_radius")
                sim_params = {"radius_km": sim_radius, "limit": 200}
            else:
                sim_k_bip = st.slider("K hospitales:", 1, 10, 3, key="sim_k_bip")
                sim_params = {"k": sim_k_bip, "limit": 200}
        
        # Botón para ejecutar simulación
        if selected_patient_code and st.button("🔍 Simular Conexión del Paciente", type="primary", use_container_width=True, key="sim_run"):
            with st.spinner("Generando grafo y calculando conexiones..."):
                # 1. Obtener grafo completo
                graph_data = fetch_graph(sim_graph_type, **sim_params)
                
                # 2. Obtener datos del paciente seleccionado
                selected_patient = next((p for p in patients_list if p['code'] == selected_patient_code), None)
                
                if graph_data and selected_patient:
                    # Guardar en session_state con claves diferentes
                    st.session_state["sim_result_graph"] = graph_data
                    st.session_state["sim_result_patient"] = selected_patient
                    st.session_state["sim_result_graph_type"] = sim_graph_type
                    st.session_state["sim_result_params"] = sim_params
                    st.rerun()
        
        # Mostrar resultados de la simulación
        if "sim_result_graph" in st.session_state and "sim_result_patient" in st.session_state:
            graph_data = st.session_state["sim_result_graph"]
            patient = st.session_state["sim_result_patient"]
            graph_type = st.session_state["sim_result_graph_type"]
            params = st.session_state["sim_result_params"]
            
            st.success(f"✅ Simulación generada para paciente **{patient['code']}**")
            
            # Encontrar conexiones del paciente en el grafo
            patient_edges = [e for e in graph_data["edges"] if e["from"] == patient["code"]]
            
            # Información del algoritmo
            st.info(f"**Algoritmo:** {graph_data.get('algorithm', 'N/A')} | **Parámetros:** {params}")
            
            # Métricas de conexión
            st.subheader("📊 Análisis de Conexiones")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Conexiones del paciente", len(patient_edges))
            
            with col2:
                if patient_edges:
                    avg_distance = sum(e["weight"] for e in patient_edges) / len(patient_edges)
                    st.metric("Distancia promedio", f"{avg_distance:.2f} km")
                else:
                    st.metric("Distancia promedio", "N/A")
            
            with col3:
                if patient_edges:
                    min_distance = min(e["weight"] for e in patient_edges)
                    st.metric("Hospital más cercano", f"{min_distance:.2f} km")
                else:
                    st.metric("Hospital más cercano", "N/A")
            
            # Tabla de conexiones
            if patient_edges:
                st.subheader("🔗 Conexiones Detectadas")
                
                connections_df = pd.DataFrame([{
                    "Nodo Destino": e["to"],
                    "Distancia (km)": f"{e['weight']:.2f}",
                    "Tipo": "Hospital" if e["to"].startswith("H") else "Otro"
                } for e in patient_edges])
                
                st.dataframe(connections_df, use_container_width=True)
            else:
                st.warning("⚠️ Este paciente no tiene conexiones en el grafo generado. Intenta con otros parámetros.")
            
            # Visualización en mapa
            st.divider()
            st.subheader("🗺️ Visualización de Conexiones en el Mapa")
            
            # Crear mapa centrado en el paciente
            m = folium.Map(
                location=[patient["lat"], patient["lon"]],
                zoom_start=8
            )
            
            # Nodos del grafo (solo cercanos al paciente para no saturar)
            nodes_dict = {n["id"]: n for n in graph_data["nodes"]}
            
            # Dibujar aristas del grafo (opacidad baja)
            for edge in graph_data["edges"][:500]:  # Limitar para performance
                from_node = nodes_dict.get(edge["from"])
                to_node = nodes_dict.get(edge["to"])
                
                if from_node and to_node:
                    folium.PolyLine(
                        locations=[
                            [from_node["lat"], from_node["lon"]],
                            [to_node["lat"], to_node["lon"]]
                        ],
                        color="#95a5a6",
                        weight=1,
                        opacity=0.1
                    ).add_to(m)
            
            # Dibujar CONEXIONES DEL PACIENTE SELECCIONADO (destacadas)
            for edge in patient_edges:
                to_node = nodes_dict.get(edge["to"])
                
                if to_node:
                    # Línea gruesa y visible
                    folium.PolyLine(
                        locations=[
                            [patient["lat"], patient["lon"]],
                            [to_node["lat"], to_node["lon"]]
                        ],
                        color="#27AE60",  # Verde brillante
                        weight=3,
                        opacity=0.8,
                        tooltip=f"Distancia: {edge['weight']:.2f} km"
                    ).add_to(m)
                    
                    # Marcador del nodo conectado
                    folium.CircleMarker(
                        location=[to_node["lat"], to_node["lon"]],
                        radius=6,
                        color="#3498DB",
                        fill=True,
                        fillColor="#3498DB",
                        fillOpacity=0.8,
                        popup=f"<b>{to_node['id']}</b><br>Distancia: {edge['weight']:.2f} km",
                        tooltip=f"🏥 {to_node['id']}"
                    ).add_to(m)
            
            # Marcador del PACIENTE (grande y destacado)
            folium.Marker(
                location=[patient["lat"], patient["lon"]],
                popup=f"<b>PACIENTE:</b> {patient['code']}<br><b>Enfermedad:</b> {patient.get('disease', 'N/A')}<br><b>Departamento:</b> {patient.get('department', 'N/A')}",
                icon=folium.Icon(color="red", icon="user", prefix="fa"),
                tooltip=f"👤 {patient['code']} (SELECCIONADO)"
            ).add_to(m)
            
            # Agregar círculo de radio si es grafo de radio
            if graph_type == "radius":
                folium.Circle(
                    location=[patient["lat"], patient["lon"]],
                    radius=params.get("radius_km", 50) * 1000,  # a metros
                    color="#E74C3C",
                    fill=False,
                    weight=2,
                    opacity=0.5,
                    tooltip=f"Radio: {params.get('radius_km', 50)} km"
                ).add_to(m)
            
            st_folium(m, width=1100, height=650, key="simulation_connection_map")
            
            # Explicación del algoritmo
            st.divider()
            st.subheader("💡 Explicación del Algoritmo")
            
            if graph_type == "knn":
                st.markdown(f"""
                **Algoritmo KNN (K-Nearest Neighbors) con K={params.get('k', 5)}**
                
                1. Se calculan las distancias del paciente **{patient['code']}** a TODOS los nodos del grafo
                2. Se seleccionan los **{params.get('k', 5)} nodos más cercanos**
                3. Se crean aristas entre el paciente y esos {params.get('k', 5)} nodos
                4. El peso de cada arista es la distancia geográfica en km
                
                ✅ En el mapa: Las **líneas verdes** muestran las {len(patient_edges)} conexiones creadas
                """)
            
            elif graph_type == "radius":
                st.markdown(f"""
                **Algoritmo de Radio (ε-vecindario) con Radio={params.get('radius_km', 50)} km**
                
                1. Se define un radio de **{params.get('radius_km', 50)} km** alrededor del paciente **{patient['code']}**
                2. Se conecta con TODOS los nodos dentro de ese radio
                3. El círculo rojo en el mapa muestra la zona de búsqueda
                4. Solo se crean aristas si la distancia ≤ {params.get('radius_km', 50)} km
                
                ✅ En el mapa: Las **líneas verdes** muestran las {len(patient_edges)} conexiones dentro del radio
                """)
            
            else:  # bipartite
                st.markdown(f"""
                **Algoritmo Bipartito KNN con K={params.get('k', 3)}**
                
                1. Este algoritmo solo conecta **pacientes → hospitales** (grafo bipartito)
                2. El paciente **{patient['code']}** se conecta a los **{params.get('k', 3)} hospitales más cercanos**
                3. NO hay conexiones paciente-paciente ni hospital-hospital
                4. Es el más eficiente para asignación directa
                
                ✅ En el mapa: Las **líneas verdes** muestran las {len(patient_edges)} conexiones a hospitales
                """)
            
            # Comparación con otros algoritmos
            with st.expander("📊 ¿Cómo se compara con otros algoritmos?"):
                st.markdown("""
                | Algoritmo | Ventajas | Desventajas |
                |-----------|----------|-------------|
                | **KNN** | Garantiza K conexiones, balanceado | Puede conectar nodos lejanos si no hay cercanos |
                | **Radio** | Solo conecta nodos cercanos, eficiente | Puede dejar nodos sin conexiones |
                | **Bipartito** | Directo, solo pac→hosp, rápido | No considera rutas indirectas |
                """)
        
        else:
            st.info("👆 Selecciona un paciente y presiona **Simular Conexión** para ver cómo se conecta al grafo")