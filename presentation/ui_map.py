# presentation/ui_map.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import pandas as pd

from shared.config import MAP_WIDTH, MAP_HEIGHT, DEFAULT_TOP_K, DEPARTAMENTO_COORDS
from infrastructure.geo_utils import hospitales_cercanos
from application.assignment_service import AssignmentService


def show_map(pacientes_df, hosp_state_df):
    st.header("  Mapa interactivo — Rutas reales con OpenRouteService")

    # Inicializar servicio de asignación
    if "assignment_service" not in st.session_state:
        st.session_state["assignment_service"] = AssignmentService(hosp_state_df)

    assignment_service = st.session_state["assignment_service"]

    # Filtros
    col1, col2 = st.columns(2)
    
    with col1:
        gravedad_filter = st.multiselect(
            "Filtrar por gravedad",
            options=sorted(pacientes_df["Gravedad"].unique().tolist()),
            default=sorted(pacientes_df["Gravedad"].unique().tolist()),
        )

    with col2:
        # Verificar si hay columna Departamento
        if "Departamento" in pacientes_df.columns:
            departamentos_disponibles = sorted(pacientes_df["Departamento"].unique().tolist())
            departamento_filter = st.multiselect(
                "Filtrar por departamento",
                options=departamentos_disponibles,
                default=departamentos_disponibles,
            )
        else:
            departamento_filter = None

    # Aplicar filtros
    pacientes_vis = pacientes_df[pacientes_df["Gravedad"].isin(gravedad_filter)].copy()
    if departamento_filter:
        pacientes_vis = pacientes_vis[
            pacientes_vis["Departamento"].isin(departamento_filter)
        ]

    st.markdown(f"**Mostrando {len(pacientes_vis)} pacientes (filtrados)**")

    # Selector de paciente
    st.markdown("---")
    st.subheader("  Explorar asignación de paciente")

    paciente_sel = st.selectbox(
        "Selecciona un paciente para ver su asignación óptima:",
        options=["Ninguno"] + pacientes_vis["ID_Paciente"].tolist(),
        index=0,
    )

    # Información del paciente seleccionado
    resultado_asignacion = None
    p_row = None

    if paciente_sel != "Ninguno":
        p_row = pacientes_df[pacientes_df["ID_Paciente"] == paciente_sel].iloc[0]
        
        # Mostrar información del paciente
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ID Paciente", p_row["ID_Paciente"])
        with col2:
            st.metric("Gravedad", p_row["Gravedad"])
        with col3:
            dept = p_row.get("Departamento", "N/A")
            st.metric("Departamento", dept)
        with col4:
            enfermedad = p_row.get("Enfermedad", "N/A")
            st.metric("Enfermedad", enfermedad[:20] + "..." if len(str(enfermedad)) > 20 else enfermedad)

        # Procesar asignación
        with st.spinner("Calculando mejor asignación y ruta real..."):
            resultado_asignacion = assignment_service.process_patient_assignment(
                p_row, hosp_state_df
            )

            # Agrega esto para debugging:
            if resultado_asignacion["ruta"] and not resultado_asignacion["ruta"]["success"]:
                st.error(f"Debug - Error de ruta: {resultado_asignacion['ruta'].get('error')}")
                if "details" in resultado_asignacion["ruta"]:
                    with st.expander("Ver detalles técnicos"):
                        st.json(resultado_asignacion["ruta"])

        # Mostrar resultados de asignación
        if resultado_asignacion["hospital_asignado"]:
            st.success(resultado_asignacion["mensaje"])
            
            # Información del hospital asignado
            hospital_asignado = hosp_state_df[
                hosp_state_df["ID_Hospital"] == resultado_asignacion["hospital_asignado"]
            ].iloc[0]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Hospital Asignado", hospital_asignado["ID_Hospital"])
            with col2:
                dist_text = f"{resultado_asignacion['distancia_km']:.2f} km" if resultado_asignacion['distancia_km'] else "N/A"
                st.metric("Distancia", dist_text)
            with col3:
                if resultado_asignacion["ufds_activado"]:
                    st.metric("UFDS", "Activado", delta="Interdepartamental")
                else:
                    st.metric("UFDS", "No necesario")

            # Información de ruta
            if resultado_asignacion["ruta"] and resultado_asignacion["ruta"]["success"]:
                ruta = resultado_asignacion["ruta"]
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Distancia real (ruta)", f"{ruta['distance']:.2f} km")
                with col2:
                    st.metric("Tiempo estimado", f"{ruta['duration']:.0f} min")
            elif resultado_asignacion["ruta"]:
                st.warning(f"  No se pudo obtener ruta: {resultado_asignacion['ruta'].get('error', 'Error desconocido')}")

            # Información del hospital
            st.markdown("**Detalles del hospital:**")
            st.dataframe(
                hospital_asignado[[
                    "ID_Hospital", "Nombre", "Departamento" if "Departamento" in hospital_asignado else "Distrito",
                    "Capacidad_Camas", "Camas_UCI", "Especialidades"
                ]].to_frame().T,
                use_container_width=True
            )

        else:
            st.error(resultado_asignacion["mensaje"])

    # Crear mapa
    st.markdown("---")
    st.subheader("Visualización del mapa")

    # Determinar centro del mapa
    if p_row is not None:
        dept_paciente = p_row.get("Departamento", "Lima")
        center_coords = DEPARTAMENTO_COORDS.get(dept_paciente, [-12.0464, -77.0428])
        zoom_start = 9
    else:
        center_coords = [-12.0464, -77.0428]
        zoom_start = 6

    m = folium.Map(location=center_coords, zoom_start=zoom_start)

    # Añadir hospitales del departamento relevante
    if p_row is not None and "Departamento" in hosp_state_df.columns:
        dept = p_row.get("Departamento")
        hospitales_vis = hosp_state_df[hosp_state_df["Departamento"] == dept]
        
        # Si UFDS activado, agregar también hospitales del departamento unido
        if resultado_asignacion and resultado_asignacion["ufds_activado"]:
            for dept_unido in resultado_asignacion["departamentos_unidos"]:
                hosp_dept = hosp_state_df[hosp_state_df["Departamento"] == dept_unido]
                hospitales_vis = pd.concat([hospitales_vis, hosp_dept]).drop_duplicates()
    else:
        hospitales_vis = hosp_state_df

    # Dibujar hospitales
    for _, h in hospitales_vis.iterrows():
        es_asignado = (
            resultado_asignacion
            and resultado_asignacion["hospital_asignado"] == h["ID_Hospital"]
        )
        
        if es_asignado:
            color = "green"
            icon = folium.Icon(color="green", icon="plus-sign")
        else:
            color = "blue" if int(h["Capacidad_Camas"]) > 0 else "gray"
            icon = None

        popup_html = f"""
        <b>{h['ID_Hospital']}</b><br>
        {h.get('Nombre', 'N/A')}<br>
        Camas: {h['Capacidad_Camas']}<br>
        UCI: {h.get('Camas_UCI', 0)}<br>
        Dept: {h.get('Departamento', h.get('Distrito', 'N/A'))}
        """

        if icon:
            folium.Marker(
                location=[float(h["Latitud"]), float(h["Longitud"])],
                popup=folium.Popup(popup_html, max_width=300),
                icon=icon,
            ).add_to(m)
        else:
            folium.CircleMarker(
                location=[float(h["Latitud"]), float(h["Longitud"])],
                radius=7,
                color=color,
                fill=True,
                fill_color=color,
                popup=folium.Popup(popup_html, max_width=300),
            ).add_to(m)

    # Dibujar paciente seleccionado
    if p_row is not None:
        folium.Marker(
            location=[float(p_row["Latitud"]), float(p_row["Longitud"])],
            popup=f"<b>Paciente {p_row['ID_Paciente']}</b><br>Gravedad: {p_row['Gravedad']}<br>Dept: {p_row.get('Departamento', 'N/A')}",
            icon=folium.Icon(color="red", icon="user"),
        ).add_to(m)

        # Dibujar ruta real si existe, o línea recta como fallback
        if resultado_asignacion and resultado_asignacion["hospital_asignado"]:
            hospital_asignado = hosp_state_df[
                hosp_state_df["ID_Hospital"] == resultado_asignacion["hospital_asignado"]
            ].iloc[0]
            
            color_ruta = "green" if resultado_asignacion["ufds_activado"] else "blue"
            
            if resultado_asignacion["ruta"] and resultado_asignacion["ruta"]["success"]:
                # Ruta real de ORS disponible
                ruta = resultado_asignacion["ruta"]
                # Convertir coordenadas de [lon, lat] a [lat, lon] para Folium
                coords_folium = [[lat, lon] for lon, lat in ruta["geometry"]]
                
                folium.PolyLine(
                    locations=coords_folium,
                    color=color_ruta,
                    weight=4,
                    opacity=0.8,
                    tooltip=f"Ruta real: {ruta['distance']:.2f} km, {ruta['duration']:.0f} min",
                ).add_to(m)
            else:
                # Fallback: línea recta (geodésica)
                folium.PolyLine(
                    locations=[
                        [float(p_row["Latitud"]), float(p_row["Longitud"])],
                        [float(hospital_asignado["Latitud"]), float(hospital_asignado["Longitud"])]
                    ],
                    color=color_ruta,
                    weight=3,
                    opacity=0.6,
                    dash_array="10",
                    tooltip=f"Línea recta (ruta real no disponible): {resultado_asignacion['distancia_km']:.2f} km",
                ).add_to(m)
                st.warning("  Mostrando línea recta estimada (ruta por carretera no disponible)")

        # Si hay grafo UFDS, dibujar conexión entre departamentos
        if resultado_asignacion and resultado_asignacion["ufds_activado"]:
            st.info(f"🔗 **UFDS Activado**: Conexión entre {' ↔ '.join(resultado_asignacion['departamentos_unidos'])}")

    # Cluster para otros pacientes (si no hay paciente seleccionado o queremos mostrar todos)
    if paciente_sel == "Ninguno":
        cluster = MarkerCluster().add_to(m)
        for _, p in pacientes_vis.head(100).iterrows():  # Limitar a 100 para performance
            folium.CircleMarker(
                location=[float(p["Latitud"]), float(p["Longitud"])],
                radius=4,
                color="red",
                fill=True,
                fill_color="red",
                popup=f"{p['ID_Paciente']} ({p['Gravedad']}) - {p.get('Departamento', p.get('Distrito', 'N/A'))}",
            ).add_to(cluster)

    # Renderizar mapa
    st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="map_main")

    # Información adicional
    with st.expander("  Información sobre el sistema"):
        st.markdown("""
        ### Cómo funciona:
        
        1. **Selección de paciente**: Elige un paciente para ver su asignación óptima
        2. **Búsqueda en departamento**: El sistema busca primero hospitales con la especialidad requerida en el departamento del paciente
        3. **UFDS (Union-Find)**: Si no hay disponibilidad local, el sistema une grafos de departamentos vecinos
        4. **Rutas reales**: Usa OpenRouteService para calcular rutas reales por carretera
        5. **Visualización**: Muestra la ruta óptima considerando distancia y especialización
        """)