# presentation/ui_map.py
from typing import Optional
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

from shared.config import CENTER_COORDS, MAP_WIDTH, MAP_HEIGHT, DEFAULT_TOP_K
from infrastructure.geo_utils import hospitales_cercanos


def show_map(pacientes_df, hosp_state_df):
    st.header("Mapa interactivo — Pacientes y hospitales")
    gravedad_filter = st.multiselect(
        "Filtrar por gravedad",
        options=sorted(pacientes_df["Gravedad"].unique().tolist()),
        default=sorted(pacientes_df["Gravedad"].unique().tolist()),
    )
    top_k = st.slider("Top k hospitales cercanos por paciente", min_value=1, max_value=10, value=DEFAULT_TOP_K)

    pacientes_vis = pacientes_df[pacientes_df["Gravedad"].isin(gravedad_filter)].reset_index(drop=True)

    st.markdown(f"Mostrando {len(pacientes_vis)} pacientes (filtrados).")
    m = folium.Map(location=CENTER_COORDS, zoom_start=11)

    # Añadir hospitales
    for _, h in hosp_state_df.iterrows():
        popup = folium.Popup(
            f"{h['ID_Hospital']} - {h.get('Nombre','')}<br>Camas: {h['Capacidad_Camas']}<br>UCI: {h.get('Camas_UCI',0)}",
            max_width=300,
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

    paciente_sel = st.selectbox("Selecciona paciente para explorar (o 'None')", options=["None"] + pacientes_vis["ID_Paciente"].tolist())
    if paciente_sel != "None":
        p_row = pacientes_df[pacientes_df["ID_Paciente"] == paciente_sel].iloc[0]
        folium.Marker(
            location=[float(p_row["Latitud"]), float(p_row["Longitud"])],
            popup=f"Paciente {p_row['ID_Paciente']} ({p_row['Gravedad']})",
            icon=folium.Icon(color="red"),
        ).add_to(m)
        top_h = hospitales_cercanos(p_row, hosp_state_df, top_k=top_k)
        st.table(top_h[["ID_Hospital", "Nombre", "Distrito", "Capacidad_Camas", "Camas_UCI", "dist_km"]])
        for _, h in top_h.iterrows():
            folium.PolyLine(
                locations=[(float(p_row["Latitud"]), float(p_row["Longitud"])), (float(h["Latitud"]), float(h["Longitud"]))],
                color="green",
                weight=2,
                opacity=0.7,
            ).add_to(m)

    # Cluster para pacientes
    cluster = MarkerCluster().add_to(m)
    for _, p in pacientes_vis.iterrows():
        folium.CircleMarker(
            location=[float(p["Latitud"]), float(p["Longitud"])],
            radius=4,
            color="red",
            fill=True,
            fill_color="red",
            popup=f"{p['ID_Paciente']} ({p['Gravedad']}) - {p.get('Distrito','')}",
        ).add_to(cluster)

    st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="map_main")
