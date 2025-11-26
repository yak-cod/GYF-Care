# presentation/ui_routes.py - VERSIÓN CORREGIDA
import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

from infrastructure.route_service import RouteService
from shared.config import MAP_WIDTH, MAP_HEIGHT, DEPARTAMENTO_COORDS

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
        # Convertir a DataFrame
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
        # Convertir a DataFrame
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


def create_map_with_route(patient, hospital, route_coords=None):
    """Crea un mapa con el paciente, hospital y ruta."""
    # Centro del mapa en el punto medio
    center_lat = (patient["lat"] + hospital["lat"]) / 2
    center_lon = (patient["lon"] + hospital["lon"]) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        width=MAP_WIDTH,
        height=MAP_HEIGHT
    )
    
    # Marcador del paciente (rojo)
    folium.Marker(
        location=[patient["lat"], patient["lon"]],
        popup=f"Paciente: {patient['code']}<br>Enfermedad: {patient.get('disease', 'N/A')}",
        icon=folium.Icon(color="red", icon="user", prefix="fa"),
        tooltip="Paciente"
    ).add_to(m)
    
    # Marcador del hospital (azul)
    folium.Marker(
        location=[hospital["lat"], hospital["lon"]],
        popup=f"Hospital: {hospital.get('name', hospital['code'])}<br>Capacidad: {hospital.get('capacity', 'N/A')}",
        icon=folium.Icon(color="blue", icon="hospital", prefix="fa"),
        tooltip="Hospital"
    ).add_to(m)
    
    # Dibujar ruta si existe
    if route_coords and len(route_coords) > 0:
        folium.PolyLine(
            locations=route_coords,
            color="green",
            weight=4,
            opacity=0.7,
            tooltip="Ruta"
        ).add_to(m)
    else:
        # Línea directa si no hay ruta de OpenRouteService
        folium.PolyLine(
            locations=[[patient["lat"], patient["lon"]], [hospital["lat"], hospital["lon"]]],
            color="gray",
            weight=2,
            opacity=0.5,
            dash_array="10",
            tooltip="Línea directa (estimada)"
        ).add_to(m)
    
    return m


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_routes_module():
    st.header("🗺️ Módulo 1: Asignación con Rutas Reales")
    st.markdown("Asigna pacientes a hospitales y visualiza rutas reales usando OpenRouteService.")
    
    # Cargar datos
    patients_df = fetch_patients()
    hospitals_df = fetch_hospitals()
    
    if patients_df.empty or hospitals_df.empty:
        st.warning("⚠️ No se pudieron cargar los datos. Verifica la conexión con el backend.")
        return
    
    # Tabs
    tab1, tab2 = st.tabs(["🏥 Asignar Paciente Único", "👥 Asignar Múltiples Pacientes"])
    
    # ================================
    # TAB 1: ASIGNAR PACIENTE ÚNICO
    # ================================
    with tab1:
        st.subheader("Asignar un paciente al mejor hospital")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
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
                filtered_patients = patients_df
            
            # Selector de paciente
            patient_options = {
                f"{row['code']} - {row.get('disease', 'N/A')} ({row['severity']})": row['code']
                for _, row in filtered_patients.iterrows()
            }
            
            if not patient_options:
                st.warning("No hay pacientes en este departamento.")
                return
            
            selected_patient_label = st.selectbox(
                "Seleccionar paciente:",
                list(patient_options.keys()),
                key="patient_single"
            )
            patient_code = patient_options[selected_patient_label]
        
        with col2:
            st.metric("Pacientes disponibles", len(filtered_patients))
            st.metric("Hospitales en el sistema", len(hospitals_df))
        
        # Botón de asignación
        if st.button("🔍 Asignar Hospital Óptimo", type="primary", use_container_width=True, key="assign_single"):
            with st.spinner("Calculando la mejor asignación..."):
                result = assign_best_hospital(patient_code)
            
            if result:
                # Guardar en session_state para evitar que desaparezca
                st.session_state["assignment_result"] = result
                st.session_state["assignment_patient_code"] = patient_code
        
        # Mostrar resultados desde session_state
        if "assignment_result" in st.session_state and st.session_state.get("assignment_patient_code") == patient_code:
            result = st.session_state["assignment_result"]
            
            if result:
                st.success(f"✅ Paciente asignado exitosamente")
                
                # Información del paciente
                patient = result["patient"]
                hospital = result["hospital"]
                distance = result.get("distance_geo_km", 0)
                algorithm = result.get("algorithm_used", "N/A")
                
                # Mostrar info
                col1, col2, col3 = st.columns(3)
                col1.metric("Algoritmo usado", algorithm)
                col2.metric("Distancia directa", f"{distance:.2f} km")
                col3.metric("Hospital", hospital.get("name", hospital["code"]))
                
                # Obtener ruta real de OpenRouteService
                route_service = RouteService()
                route_data = route_service.get_route(
                    patient["lat"], patient["lon"],
                    hospital["lat"], hospital["lon"]
                )
                
                if route_data and route_data.get("success") and "geometry" in route_data:
                    # geometry viene como [[lon, lat], [lon, lat], ...]
                    route_coords = [[lat, lon] for lon, lat in route_data["geometry"]]
                    distance_real = route_data.get("distance", 0)  # ya viene en km
                    duration = route_data.get("duration", 0)  # ya viene en minutos
                    
                    st.info(f"🚗 Ruta real: {distance_real:.2f} km | ⏱️ {duration:.0f} minutos")
                else:
                    route_coords = None
                    st.warning("⚠️ No se pudo obtener la ruta real de OpenRouteService. Mostrando línea directa.")
                
                # Crear y mostrar mapa
                st.subheader("📍 Mapa de Ruta")
                m = create_map_with_route(patient, hospital, route_coords)
                st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="route_map_single")
                
                # Detalles adicionales
                with st.expander("📊 Ver detalles completos"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Paciente:**")
                        st.json({
                            "Código": patient["code"],
                            "Enfermedad": patient.get("disease", "N/A"),
                            "Gravedad": patient.get("severity", "N/A"),
                            "Departamento": patient.get("department", "N/A"),
                        })
                    
                    with col2:
                        st.markdown("**Hospital:**")
                        st.json({
                            "Código": hospital["code"],
                            "Nombre": hospital.get("name", "N/A"),
                            "Especialidades": hospital.get("specialties", "N/A"),
                            "Capacidad": hospital.get("capacity", "N/A"),
                        })
    
    # ================================
    # TAB 2: ASIGNAR MÚLTIPLES
    # ================================
    with tab2:
        st.subheader("Asignar múltiples pacientes")
        st.info("💡 Selecciona varios pacientes para asignarlos y ver todas las rutas en el mapa.")
        
        # Filtro por departamento
        departments = ["Todos"] + sorted(patients_df["department"].dropna().unique().tolist())
        selected_dept_multi = st.selectbox(
            "Filtrar por departamento:",
            departments,
            key="dept_multi"
        )
        
        # Filtrar pacientes
        if selected_dept_multi != "Todos":
            filtered_patients_multi = patients_df[patients_df["department"] == selected_dept_multi]
        else:
            filtered_patients_multi = patients_df
        
        # Multi-select de pacientes
        num_patients = st.slider(
            "Número de pacientes a asignar:",
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
        
        if st.button("🔍 Asignar Hospitales a Todos", type="primary", use_container_width=True, key="assign_multiple"):
            if not selected_patients:
                st.warning("⚠️ Selecciona al menos un paciente.")
            else:
                with st.spinner(f"Asignando {len(selected_patients)} pacientes..."):
                    assignments = []
                    
                    for patient_code in selected_patients:
                        result = assign_best_hospital(patient_code)
                        if result:
                            assignments.append(result)
                
                # Guardar en session_state
                st.session_state["multiple_assignments"] = assignments
                st.session_state["multiple_patient_codes"] = selected_patients
        
        # Mostrar resultados desde session_state
        if "multiple_assignments" in st.session_state and st.session_state.get("multiple_patient_codes") == selected_patients:
            assignments = st.session_state["multiple_assignments"]
            
            if assignments:
                st.success(f"✅ {len(assignments)} pacientes asignados exitosamente")
                
                # Obtener rutas reales usando OpenRouteService
                with st.spinner("🗺️ Calculando rutas reales..."):
                    route_service = RouteService()
                    
                    # Preparar orígenes y destinos
                    origins = [(a["patient"]["lat"], a["patient"]["lon"]) for a in assignments]
                    destinations = [(a["hospital"]["lat"], a["hospital"]["lon"]) for a in assignments]
                    
                    # Obtener todas las rutas
                    routes = route_service.get_multiple_routes(origins, destinations)
                
                # Crear mapa con todas las asignaciones
                m = folium.Map(location=[-9.19, -75.01], zoom_start=6, width=MAP_WIDTH, height=MAP_HEIGHT)
                
                colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "darkblue", "cadetblue", "darkgreen"]
                
                # Tabla resumen (con distancias reales)
                summary_data = []
                
                for idx, (assignment, route) in enumerate(zip(assignments, routes)):
                    patient = assignment["patient"]
                    hospital = assignment["hospital"]
                    color = colors[idx % len(colors)]
                    
                    # Marcador paciente
                    folium.Marker(
                        location=[patient["lat"], patient["lon"]],
                        popup=f"<b>Paciente:</b> {patient['code']}<br><b>Enfermedad:</b> {patient.get('disease', 'N/A')}",
                        icon=folium.Icon(color=color, icon="user", prefix="fa"),
                        tooltip=f"Paciente {patient['code']}"
                    ).add_to(m)
                    
                    # Marcador hospital
                    folium.Marker(
                        location=[hospital["lat"], hospital["lon"]],
                        popup=f"<b>Hospital:</b> {hospital.get('name', hospital['code'])}",
                        icon=folium.Icon(color="blue", icon="hospital", prefix="fa"),
                        tooltip=f"Hospital {hospital['code']}"
                    ).add_to(m)
                    
                    # Dibujar ruta real o línea directa
                    if route and route.get("success") and "geometry" in route:
                        # Ruta real de OpenRouteService
                        route_coords = [[lat, lon] for lon, lat in route["geometry"]]
                        folium.PolyLine(
                            locations=route_coords,
                            color=color,
                            weight=3,
                            opacity=0.8,
                            tooltip=f"Ruta {patient['code']} → {hospital['code']}"
                        ).add_to(m)
                        
                        distance_real = route.get("distance", 0)
                        duration = route.get("duration", 0)
                    else:
                        # Línea directa (fallback)
                        folium.PolyLine(
                            locations=[[patient["lat"], patient["lon"]], [hospital["lat"], hospital["lon"]]],
                            color=color,
                            weight=2,
                            opacity=0.5,
                            dash_array="10"
                        ).add_to(m)
                        
                        distance_real = assignment.get('distance_geo_km', 0)
                        duration = None
                    
                    # Agregar a tabla resumen
                    summary_data.append({
                        "Paciente": patient['code'],
                        "Enfermedad": patient.get('disease', 'N/A')[:30],
                        "Hospital": hospital.get('name', hospital['code'])[:40],
                        "Dist. Real (km)": f"{distance_real:.2f}" if distance_real else "N/A",
                        "Tiempo (min)": f"{duration:.0f}" if duration else "N/A",
                        "Algoritmo": assignment.get('algorithm_used', 'N/A'),
                    })
                
                st.subheader("📍 Mapa con Todas las Rutas Reales")
                st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="route_map_multiple")
                
                # Tabla resumen con distancias y tiempos reales
                st.subheader("📊 Resumen de Asignaciones (con rutas reales)")
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
                
                # Estadísticas agregadas
                col1, col2, col3 = st.columns(3)
                total_distance = sum([float(d["Dist. Real (km)"]) for d in summary_data if d["Dist. Real (km)"] != "N/A"])
                total_time = sum([float(d["Tiempo (min)"]) for d in summary_data if d["Tiempo (min)"] != "N/A"])
                avg_distance = total_distance / len(summary_data) if summary_data else 0
                
                col1.metric("📏 Distancia Total", f"{total_distance:.2f} km")
                col2.metric("⏱️ Tiempo Total", f"{total_time:.0f} min")
                col3.metric("📊 Distancia Promedio", f"{avg_distance:.2f} km")