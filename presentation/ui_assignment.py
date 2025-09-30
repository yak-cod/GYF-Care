# presentation/ui_assignment.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

from application.assignment_service import run_greedy, run_min_cost_flow
from shared.config import MAP_WIDTH, MAP_HEIGHT, CENTER_COORDS
from infrastructure.geo_utils import hospitales_cercanos

def show_assignment(pacientes_df: pd.DataFrame, hosp_state: pd.DataFrame):
    st.header("Módulo de asignación")
    st.markdown("Puedes elegir heurística greedy o Min-Cost Max-Flow (óptimo, puede tardar).")

    metodo = st.radio("Método", options=["Greedy (rápido)", "Min-Cost Max-Flow (óptimo)"])
    pacientes_to_assign = st.multiselect(
        "Selecciona pacientes a asignar (muestra)",
        options=pacientes_df["ID_Paciente"].tolist(),
        default=pacientes_df["ID_Paciente"].tolist()[:50],
    )

    if st.button("Ejecutar asignación"):
        if metodo == "Greedy (rápido)":
            asign_df, hosp_nuevo = run_greedy(pacientes_df, hosp_state, pacientes_to_assign)
            st.session_state.hosp_state = hosp_nuevo
            st.session_state["asign_df"] = asign_df
            st.success("Asignación greedy ejecutada")
        else:
            with st.spinner("Ejecutando Min-Cost Max-Flow (puede tardar)..."):
                asign_df, error, hosp_nuevo = run_min_cost_flow(
                    pacientes_df[pacientes_df["ID_Paciente"].isin(pacientes_to_assign)],
                    hosp_state,
                )
                if error:
                    st.error(f"No se pudo ejecutar min-cost flow: {error}")
                    st.session_state["asign_df"] = pd.DataFrame()
                else:
                    st.session_state.hosp_state = hosp_nuevo
                    st.session_state["asign_df"] = asign_df
                    st.success("Asignación Min-Cost Max-Flow ejecutada")

    # Mostrar resultados si existen
    if "asign_df" in st.session_state and not st.session_state["asign_df"].empty:
        asign_df = st.session_state["asign_df"]
        total_pacientes = len(asign_df)
        asignados = asign_df["ID_Hospital"].notna().sum()
        no_asignados = total_pacientes - asignados

        total_hosp = len(st.session_state.hosp_state)
        hosp_con_cap = (st.session_state.hosp_state["Capacidad_Camas"] > 0).sum()
        hosp_sin_cap = total_hosp - hosp_con_cap
        total_camas_restantes = int(st.session_state.hosp_state["Capacidad_Camas"].sum())

        st.markdown("### Estado general")
        colA, colB, colC = st.columns(3)
        colA.metric("Pacientes asignados", int(asignados), f"{(asignados/total_pacientes*100):.1f}%" if total_pacientes > 0 else "0%")
        colB.metric("No asignados", int(no_asignados))
        colC.metric("Total pacientes (lote)", int(total_pacientes))

        colD, colE, colF = st.columns(3)
        colD.metric("Hosp. con capacidad", int(hosp_con_cap))
        colE.metric("Hosp. saturados", int(hosp_sin_cap))
        colF.metric("Camas restantes", int(total_camas_restantes))

        # Controles de visualización
        st.subheader("Filtros de visualización")
        mostrar_no_asignados = st.checkbox("Mostrar pacientes NO asignados", value=True)
        filtro_gravedad = st.multiselect(
            "Filtrar por gravedad",
            options=["Leve", "Moderado", "Crítico"],
            default=["Leve", "Moderado", "Crítico"],
        )

        # Mapa
        st.subheader("Mapa de asignaciones")
        lat_mean = asign_df.merge(pacientes_df, on="ID_Paciente")["Latitud"].mean()
        lon_mean = asign_df.merge(pacientes_df, on="ID_Paciente")["Longitud"].mean()
        center = [lat_mean if not pd.isna(lat_mean) else CENTER_COORDS[0], lon_mean if not pd.isna(lon_mean) else CENTER_COORDS[1]]

        m = folium.Map(location=center, zoom_start=11)

        # Hospitales
        for _, h in st.session_state.hosp_state.iterrows():
            popup = folium.Popup(
                f"{h['ID_Hospital']} - {h.get('Nombre','')}<br>Camas: {h['Capacidad_Camas']}<br>UCI: {h.get('Camas_UCI',0)}", max_width=300
            )
            hosp_color = "blue" if int(h["Capacidad_Camas"]) > 0 else "gray"
            folium.CircleMarker(
                location=[float(h["Latitud"]), float(h["Longitud"])],
                radius=7,
                color=hosp_color,
                fill=True,
                fill_color=hosp_color,
                popup=popup,
            ).add_to(m)

        # Cluster de pacientes
        cluster = MarkerCluster().add_to(m)
        severity_map = {"Leve": 4, "Moderado": 7, "Crítico": 10}

        for _, row in asign_df.iterrows():
            p_row = pacientes_df[pacientes_df["ID_Paciente"] == row["ID_Paciente"]].iloc[0]
            gravedad = p_row.get("Gravedad", "Leve")
            if gravedad not in filtro_gravedad:
                continue
            lat_p, lon_p = float(p_row["Latitud"]), float(p_row["Longitud"])

            if row["ID_Hospital"] is None:
                color = "orange"
                popup_text = f"Paciente {row['ID_Paciente']} ({gravedad}) - NO asignado"
            else:
                color = "green"
                h_row = st.session_state.hosp_state[st.session_state.hosp_state["ID_Hospital"] == row["ID_Hospital"]].iloc[0]
                lat_h, lon_h = float(h_row["Latitud"]), float(h_row["Longitud"])
                popup_text = f"Paciente {row['ID_Paciente']} ({gravedad}) → Hospital {row['ID_Hospital']}"
                folium.PolyLine([(lat_p, lon_p), (lat_h, lon_h)], color="green", weight=2, opacity=0.7).add_to(m)

            if (row["ID_Hospital"] is None) and (not mostrar_no_asignados):
                continue

            folium.CircleMarker(
                location=[lat_p, lon_p],
                radius=severity_map.get(gravedad, 5),
                color=color,
                fill=True,
                fill_color=color,
                popup=popup_text
            ).add_to(cluster)

        st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="mapa_asignacion")

    # Estado actual de hospitales (tabla)
    st.markdown("**Estado actual de hospitales (capacidad restante)**")
    st.dataframe(
        st.session_state.hosp_state[["ID_Hospital", "Nombre", "Capacidad_Camas", "Camas_UCI", "Distrito"]].reset_index(drop=True)
    )
