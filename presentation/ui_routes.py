# presentation/ui_routes.py - VERSIÓN SIMPLIFICADA
import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px

from infrastructure.route_service import RouteService
from shared.config import MAP_WIDTH, MAP_HEIGHT

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:5000/api")

# ================================
# FUNCIONES AUXILIARES
# ================================

@st.cache_data(ttl=300)
def fetch_patients():
    """Obtiene pacientes del backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/patients", params={"limit": 1000}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return pd.DataFrame(data["patients"])
    except Exception as e:
        st.error(f"Error al cargar pacientes: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_hospitals():
    """Obtiene hospitales del backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/hospitals", timeout=10)
        response.raise_for_status()
        data = response.json()
        return pd.DataFrame(data["hospitals"])
    except Exception as e:
        st.error(f"Error al cargar hospitales: {e}")
        return pd.DataFrame()


def assign_best_hospital(patient_code: str):
    """Asigna el mejor hospital a un paciente usando el backend."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/assign/patient-best",
            json={"patient_code": patient_code},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error al asignar hospital: {e}")
        return None


def compare_algorithms_for_patient(patient_code: str):
    """Compara todos los algoritmos para un paciente."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/assign/compare-patient",
            json={"patient_code": patient_code},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error al comparar algoritmos: {e}")
        return None


def create_map_with_route(patient, hospital, route_coords=None):
    """Crea un mapa con el paciente, hospital y ruta."""
    center_lat = (patient["lat"] + hospital["lat"]) / 2
    center_lon = (patient["lon"] + hospital["lon"]) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        width=MAP_WIDTH,
        height=MAP_HEIGHT
    )
    
    # Marcador del paciente
    folium.Marker(
        location=[patient["lat"], patient["lon"]],
        popup=f"Paciente: {patient['code']}<br>Enfermedad: {patient.get('disease', 'N/A')}",
        icon=folium.Icon(color="red", icon="user", prefix="fa"),
        tooltip="Paciente"
    ).add_to(m)
    
    # Marcador del hospital
    folium.Marker(
        location=[hospital["lat"], hospital["lon"]],
        popup=f"Hospital: {hospital.get('name', hospital['code'])}<br>Capacidad: {hospital.get('capacity', 'N/A')}",
        icon=folium.Icon(color="blue", icon="hospital", prefix="fa"),
        tooltip="Hospital"
    ).add_to(m)
    
    # Dibujar ruta
    if route_coords and len(route_coords) > 0:
        folium.PolyLine(
            locations=route_coords,
            color="green",
            weight=4,
            opacity=0.7,
            tooltip="Ruta"
        ).add_to(m)
    else:
        folium.PolyLine(
            locations=[[patient["lat"], patient["lon"]], [hospital["lat"], hospital["lon"]]],
            color="gray",
            weight=2,
            opacity=0.5,
            dash_array="10",
            tooltip="Línea directa"
        ).add_to(m)
    
    return m


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_routes_module():
    st.header("Asignación de Pacientes")
    
    # Cargar datos
    patients_df = fetch_patients()
    hospitals_df = fetch_hospitals()
    
    if patients_df.empty or hospitals_df.empty:
        st.warning("No se pudieron cargar los datos. Verifica la conexión con el backend.")
        return
    
    # Tabs
    tab1, tab2 = st.tabs(["Paciente Individual", "Múltiples Pacientes"])
    
    # ================================
    # TAB 1: ASIGNAR PACIENTE ÚNICO
    # ================================
    with tab1:
        # Filtro por departamento
        departments = ["Todos"] + sorted(patients_df["department"].dropna().unique().tolist())
        selected_dept = st.selectbox(
            "Filtrar por departamento:",
            departments,
            key="dept_single"
        )
        
        # Filtrar pacientes
        if selected_dept != "Todos":
            filtered_patients = patients_df[patients_df["department"] == selected_dept]
        else:
            # LIMITAR A 100 PACIENTES PARA NO SATURAR EL MAPA
            filtered_patients = patients_df.head(100)
        
        if filtered_patients.empty:
            st.warning("No hay pacientes en este departamento.")
            return
        
        # Inicializar estado si no existe
        if "selected_patient_map" not in st.session_state:
            st.session_state["selected_patient_map"] = None
        
        # Selector manual de paciente (arriba, más visible)
        st.subheader("Seleccionar Paciente")
        
        patient_options = {
            f"{row['code']} - {row.get('disease', 'N/A')[:40]}": row['code']
            for _, row in filtered_patients.iterrows()
        }
        
        selected_patient_label = st.selectbox(
            "Buscar paciente:",
            list(patient_options.keys()),
            key="patient_single"
        )
        patient_code = patient_options[selected_patient_label]
        
        # Botón de asignación (antes del mapa para que sea más rápido)
        if st.button("Asignar Hospital", type="primary", use_container_width=True, key="assign_single"):
            # Usar un contenedor para no bloquear toda la pantalla
            with st.status("Calculando asignación...", expanded=False) as status:
                result = assign_best_hospital(patient_code)
                status.update(label="Comparando algoritmos...", state="running")
                comparison = compare_algorithms_for_patient(patient_code)
                status.update(label="Completado", state="complete")
            
            if result and comparison:
                st.session_state["assignment_result"] = result
                st.session_state["comparison_result"] = comparison
                st.session_state["assignment_patient_code"] = patient_code
        
        # Mostrar resultados
        if "assignment_result" in st.session_state and st.session_state.get("assignment_patient_code") == patient_code:
            result = st.session_state["assignment_result"]
            comparison = st.session_state.get("comparison_result")
            
            st.success("Asignación completada")
            
            patient = result["patient"]
            hospital = result["hospital"]
            distance = result.get("distance_geo_km", 0)
            algorithm = result.get("algorithm_used", "N/A")
            
            # Info de asignación
            col1, col2, col3 = st.columns(3)
            col1.metric("Algoritmo", algorithm)
            col2.metric("Distancia", f"{distance:.2f} km")
            col3.metric("Hospital", hospital.get("name", hospital["code"])[:20])
            
            # Obtener ruta real
            route_service = RouteService()
            
            with st.status("Calculando ruta real...", expanded=False) as status:
                route_data = route_service.get_route(
                    patient["lat"], patient["lon"],
                    hospital["lat"], hospital["lon"]
                )
                status.update(label="Ruta calculada", state="complete")
            
            if route_data and route_data.get("success") and "geometry" in route_data:
                route_coords = [[lat, lon] for lon, lat in route_data["geometry"]]
                distance_real = route_data.get("distance", 0)
                duration = route_data.get("duration", 0)
                st.info(f"Ruta real: {distance_real:.2f} km | {duration:.0f} min")
            else:
                route_coords = None
            
            # Mapa
            st.divider()
            m = create_map_with_route(patient, hospital, route_coords)
            st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="route_map_single")
            
            # Comparación de algoritmos
            if comparison:
                st.divider()
                st.subheader("Comparación de Algoritmos")
                
                assignment_algos = comparison.get("assignment_algorithms", [])
                
                if assignment_algos:
                    assignment_data = []
                    for algo in assignment_algos:
                        # Filtrar Greedy
                        if "greedy" in algo["name"].lower():
                            continue
                        
                        hospital_algo = algo.get("hospital")
                        if hospital_algo:
                            assignment_data.append({
                                "Algoritmo": algo["name"],
                                "Tiempo (ms)": f"{algo['time_ms']:.4f}",
                                "Hospital": hospital_algo.get("name", hospital_algo["code"])[:30],
                                "Distancia": f"{algo.get('distance_geo_km', 0):.2f} km",
                            })
                    
                    df_assignment = pd.DataFrame(assignment_data)
                    st.dataframe(df_assignment, use_container_width=True, hide_index=True)
                    
                    # Gráfico
                    if len(df_assignment) > 0:
                        fig = px.bar(
                            df_assignment,
                            x="Algoritmo",
                            y="Tiempo (ms)",
                            color="Algoritmo",
                            title="Tiempo de Ejecución"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Detalles Dijkstra vs Bellman-Ford
                    st.markdown("**Análisis de Rutas**")
                    
                    for algo in assignment_algos:
                        # Filtrar Greedy
                        if "greedy" in algo["name"].lower():
                            continue
                        
                        if algo.get("hospital") and algo.get("paths"):
                            st.markdown(f"*{algo['name']}*")
                            paths = algo["paths"]
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                dijkstra = paths.get("dijkstra")
                                if dijkstra:
                                    st.markdown("**Dijkstra**")
                                    metrics_df = pd.DataFrame([{
                                        "Métrica": "Distancia",
                                        "Valor": f"{dijkstra.get('distance', 0):.2f} km"
                                    }, {
                                        "Métrica": "Tiempo",
                                        "Valor": f"{dijkstra.get('time_ms', 0):.4f} ms"
                                    }])
                                    st.dataframe(metrics_df, hide_index=True, use_container_width=True)
                            
                            with col2:
                                bellman = paths.get("bellman_ford")
                                if bellman:
                                    st.markdown("**Bellman-Ford**")
                                    metrics_df = pd.DataFrame([{
                                        "Métrica": "Distancia",
                                        "Valor": f"{bellman.get('distance', 0):.2f} km"
                                    }, {
                                        "Métrica": "Tiempo",
                                        "Valor": f"{bellman.get('time_ms', 0):.4f} ms"
                                    }])
                                    st.dataframe(metrics_df, hide_index=True, use_container_width=True)
            
            # Información completa
            st.divider()
            st.subheader("Información Completa")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Paciente**")
                patient_info = pd.DataFrame([
                    {"Campo": "Código", "Valor": patient["code"]},
                    {"Campo": "Enfermedad", "Valor": patient.get("disease", "N/A")},
                    {"Campo": "Gravedad", "Valor": patient.get("severity", "N/A")},
                    {"Campo": "Departamento", "Valor": patient.get("department", "N/A")},
                ])
                st.dataframe(patient_info, hide_index=True, use_container_width=True)
            
            with col2:
                st.markdown("**Hospital**")
                hospital_info = pd.DataFrame([
                    {"Campo": "Código", "Valor": hospital["code"]},
                    {"Campo": "Nombre", "Valor": hospital.get("name", "N/A")},
                    {"Campo": "Especialidades", "Valor": str(hospital.get("specialties", "N/A"))[:50]},
                    {"Campo": "Capacidad", "Valor": hospital.get("capacity", "N/A")},
                ])
                st.dataframe(hospital_info, hide_index=True, use_container_width=True)
    
    # ================================
    # TAB 2: MÚLTIPLES PACIENTES
    # ================================
    with tab2:
        # Filtro por departamento
        departments = ["Todos"] + sorted(patients_df["department"].dropna().unique().tolist())
        selected_dept_multi = st.selectbox(
            "Filtrar por departamento:",
            departments,
            key="dept_multi"
        )
        
        if selected_dept_multi != "Todos":
            filtered_patients_multi = patients_df[patients_df["department"] == selected_dept_multi]
        else:
            filtered_patients_multi = patients_df
        
        # Multi-select
        num_patients = st.slider(
            "Número de pacientes:",
            min_value=1,
            max_value=min(10, len(filtered_patients_multi)),
            value=3,
            key="num_patients_multi"
        )
        
        selected_patients = st.multiselect(
            "Seleccionar pacientes:",
            options=filtered_patients_multi["code"].tolist(),
            default=filtered_patients_multi["code"].tolist()[:num_patients],
            key="patients_multi"
        )
        
        if st.button("Asignar Hospitales", type="primary", use_container_width=True, key="assign_multiple"):
            if not selected_patients:
                st.warning("Selecciona al menos un paciente.")
            else:
                assignments = []
                
                # Usar progress bar en lugar de spinner
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, patient_code in enumerate(selected_patients):
                    status_text.text(f"Asignando paciente {idx + 1} de {len(selected_patients)}...")
                    result = assign_best_hospital(patient_code)
                    if result:
                        assignments.append(result)
                    progress_bar.progress((idx + 1) / len(selected_patients))
                
                progress_bar.empty()
                status_text.empty()
                
                st.session_state["multiple_assignments"] = assignments
                st.session_state["multiple_patient_codes"] = selected_patients
        
        # Mostrar resultados
        if "multiple_assignments" in st.session_state and st.session_state.get("multiple_patient_codes") == selected_patients:
            assignments = st.session_state["multiple_assignments"]
            
            if assignments:
                st.success(f"{len(assignments)} pacientes asignados")
                
                # Obtener rutas
                route_service = RouteService()
                origins = [(a["patient"]["lat"], a["patient"]["lon"]) for a in assignments]
                destinations = [(a["hospital"]["lat"], a["hospital"]["lon"]) for a in assignments]
                
                # Progress bar para rutas
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.text("Calculando rutas...")
                
                routes = route_service.get_multiple_routes(origins, destinations)
                
                progress_bar.progress(1.0)
                progress_bar.empty()
                status_text.empty()
                
                # Mapa
                m = folium.Map(location=[-9.19, -75.01], zoom_start=6, width=MAP_WIDTH, height=MAP_HEIGHT)
                
                colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "darkblue", "cadetblue", "darkgreen"]
                summary_data = []
                
                for idx, (assignment, route) in enumerate(zip(assignments, routes)):
                    patient = assignment["patient"]
                    hospital = assignment["hospital"]
                    color = colors[idx % len(colors)]
                    
                    folium.Marker(
                        location=[patient["lat"], patient["lon"]],
                        popup=f"Paciente: {patient['code']}",
                        icon=folium.Icon(color=color, icon="user", prefix="fa"),
                        tooltip=f"Paciente {patient['code']}"
                    ).add_to(m)
                    
                    folium.Marker(
                        location=[hospital["lat"], hospital["lon"]],
                        popup=f"Hospital: {hospital.get('name', hospital['code'])}",
                        icon=folium.Icon(color="blue", icon="hospital", prefix="fa"),
                        tooltip=f"Hospital {hospital['code']}"
                    ).add_to(m)
                    
                    if route and route.get("success") and "geometry" in route:
                        route_coords = [[lat, lon] for lon, lat in route["geometry"]]
                        folium.PolyLine(
                            locations=route_coords,
                            color=color,
                            weight=3,
                            opacity=0.8
                        ).add_to(m)
                        distance_real = route.get("distance", 0)
                        duration = route.get("duration", 0)
                    else:
                        folium.PolyLine(
                            locations=[[patient["lat"], patient["lon"]], [hospital["lat"], hospital["lon"]]],
                            color=color,
                            weight=2,
                            opacity=0.5,
                            dash_array="10"
                        ).add_to(m)
                        distance_real = assignment.get('distance_geo_km', 0)
                        duration = None
                    
                    summary_data.append({
                        "Paciente": patient['code'],
                        "Hospital": hospital.get('name', hospital['code'])[:30],
                        "Distancia (km)": f"{distance_real:.2f}" if distance_real else "N/A",
                        "Tiempo (min)": f"{duration:.0f}" if duration else "N/A",
                    })
                
                st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="route_map_multiple")
                
                st.divider()
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
                
                # Estadísticas
                col1, col2, col3 = st.columns(3)
                total_distance = sum([float(d["Distancia (km)"]) for d in summary_data if d["Distancia (km)"] != "N/A"])
                total_time = sum([float(d["Tiempo (min)"]) for d in summary_data if d["Tiempo (min)"] != "N/A"])
                avg_distance = total_distance / len(summary_data) if summary_data else 0
                
                col1.metric("Distancia Total", f"{total_distance:.2f} km")
                col2.metric("Tiempo Total", f"{total_time:.0f} min")
                col3.metric("Distancia Promedio", f"{avg_distance:.2f} km")