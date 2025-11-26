# presentation/ui_algorithms.py - VERSIÓN CORREGIDA
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

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


# ================================
# MÓDULO PRINCIPAL
# ================================

def show_algorithms_module():
    st.header("🔬 Módulo 3: Comparación de Algoritmos")
    st.markdown("Compara 8 algoritmos diferentes aplicados a la asignación de un paciente.")
    
    # Cargar pacientes
    patients_df = fetch_patients()
    
    if patients_df.empty:
        st.warning("⚠️ No se pudieron cargar los pacientes. Verifica la conexión con el backend.")
        return
    
    # Selector de paciente
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Filtro por departamento
        departments = ["Todos"] + sorted(patients_df["department"].dropna().unique().tolist())
        selected_dept = st.selectbox(
            "Filtrar por departamento:",
            departments,
            key="dept_comparison"
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
            "Seleccionar paciente para comparar:",
            list(patient_options.keys()),
            key="patient_comparison"
        )
        patient_code = patient_options[selected_patient_label]
    
    with col2:
        st.metric("Pacientes disponibles", len(filtered_patients))
    
    # Botón de comparación
    if st.button("⚡ Comparar 8 Algoritmos", type="primary", use_container_width=True):
        with st.spinner("Ejecutando 8 algoritmos... Esto puede tardar hasta 60 segundos."):
            result = compare_algorithms_for_patient(patient_code)
        
        if result:
            st.success("✅ Comparación completada")
            
            # Información del paciente
            patient = result["patient"]
            specialty_required = result.get("specialty_required", "N/A")
            
            st.subheader("📋 Información del Paciente")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Código", patient["code"])
            col2.metric("Enfermedad", patient.get("disease", "N/A"))
            col3.metric("Gravedad", patient.get("severity", "N/A"))
            col4.metric("Especialidad requerida", specialty_required)
            
            # ================================
            # ALGORITMOS DE ASIGNACIÓN
            # ================================
            st.divider()
            st.subheader("🎯 Algoritmos de Asignación (3)")
            st.markdown("Estos algoritmos asignan el paciente a un hospital considerando distancia y especialidad.")
            
            assignment_algos = result.get("assignment_algorithms", [])
            
            if assignment_algos:
                # Tabla comparativa
                assignment_data = []
                for algo in assignment_algos:
                    hospital = algo.get("hospital")
                    if hospital:
                        assignment_data.append({
                            "Algoritmo": algo["name"],
                            "Complejidad": algo["big_o"],
                            "Tiempo (ms)": f"{algo['time_ms']:.4f}",
                            "Hospital": hospital.get("name", hospital["code"]),
                            "Distancia (km)": f"{algo.get('distance_geo_km', 0):.2f}",
                        })
                    else:
                        assignment_data.append({
                            "Algoritmo": algo["name"],
                            "Complejidad": algo["big_o"],
                            "Tiempo (ms)": f"{algo['time_ms']:.4f}",
                            "Hospital": "❌ No asignado",
                            "Distancia (km)": "N/A",
                        })
                
                df_assignment = pd.DataFrame(assignment_data)
                st.dataframe(df_assignment, use_container_width=True)
                
                # Gráfico de tiempos
                fig_assignment = px.bar(
                    df_assignment,
                    x="Algoritmo",
                    y="Tiempo (ms)",
                    color="Algoritmo",
                    title="Tiempo de Ejecución - Algoritmos de Asignación",
                    labels={"Tiempo (ms)": "Tiempo (ms)"}
                )
                st.plotly_chart(fig_assignment, use_container_width=True)
                
                # Detalles de rutas
                with st.expander("📍 Ver rutas calculadas (Dijkstra vs Bellman-Ford)"):
                    for algo in assignment_algos:
                        if algo.get("hospital") and algo.get("paths"):
                            st.markdown(f"**{algo['name']}:**")
                            paths = algo["paths"]
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                dijkstra = paths.get("dijkstra")
                                if dijkstra:
                                    st.markdown("**Dijkstra:**")
                                    st.json({
                                        "Distancia": f"{dijkstra.get('distance', 0):.2f} km",
                                        "Tiempo": f"{dijkstra.get('time_ms', 0):.4f} ms",
                                        "Nodos en ruta": len(dijkstra.get("path_nodes", [])),
                                    })
                            
                            with col2:
                                bellman = paths.get("bellman_ford")
                                if bellman:
                                    st.markdown("**Bellman-Ford:**")
                                    st.json({
                                        "Distancia": f"{bellman.get('distance', 0):.2f} km",
                                        "Tiempo": f"{bellman.get('time_ms', 0):.4f} ms",
                                        "Nodos en ruta": len(bellman.get("path_nodes", [])),
                                    })
                            
                            st.divider()
            
            # ================================
            # ALGORITMOS DE REDES
            # ================================
            st.divider()
            st.subheader("🌐 Algoritmos de Redes (3)")
            st.markdown("Estos algoritmos analizan la red completa de pacientes y hospitales.")
            
            network_algos = result.get("network_algorithms", [])
            
            if network_algos:
                # Tabla comparativa
                network_data = []
                for algo in network_algos:
                    network_data.append({
                        "Algoritmo": algo["name"],
                        "Categoría": algo["category"],
                        "Complejidad": algo["big_o"],
                        "Tiempo (ms)": f"{algo['time_ms']:.4f}",
                    })
                
                df_network = pd.DataFrame(network_data)
                st.dataframe(df_network, use_container_width=True)
                
                # Gráfico de tiempos
                fig_network = px.bar(
                    df_network,
                    x="Algoritmo",
                    y="Tiempo (ms)",
                    color="Algoritmo",
                    title="Tiempo de Ejecución - Algoritmos de Redes",
                    labels={"Tiempo (ms)": "Tiempo (ms)"}
                )
                st.plotly_chart(fig_network, use_container_width=True)
            
            # ================================
            # COMPARACIÓN GLOBAL
            # ================================
            st.divider()
            st.subheader("📊 Comparación Global de Tiempos")
            
            all_algos_data = []
            
            for algo in assignment_algos:
                all_algos_data.append({
                    "Algoritmo": algo["name"],
                    "Categoría": "Asignación",
                    "Tiempo (ms)": algo["time_ms"],
                })
            
            for algo in network_algos:
                all_algos_data.append({
                    "Algoritmo": algo["name"],
                    "Categoría": "Redes",
                    "Tiempo (ms)": algo["time_ms"],
                })
            
            df_all = pd.DataFrame(all_algos_data)
            
            fig_all = px.bar(
                df_all,
                x="Algoritmo",
                y="Tiempo (ms)",
                color="Categoría",
                title="Comparación de Tiempos - Todos los Algoritmos",
                labels={"Tiempo (ms)": "Tiempo (ms)"},
                barmode="group"
            )
            st.plotly_chart(fig_all, use_container_width=True)
            
            # Resumen en texto
            st.info(f"""
            **Resumen:**
            - Se ejecutaron **{len(assignment_algos) + len(network_algos)} algoritmos** en total.
            - Los algoritmos de asignación encontraron hospitales adecuados para el paciente.
            - Los algoritmos de redes analizaron la estructura completa del grafo.
            """)