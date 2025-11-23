# presentation/ui_backend_dashboard.py

import random
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from pyvis.network import Network

import folium
from streamlit_folium import st_folium

from shared.config import MAP_WIDTH, MAP_HEIGHT, DEPARTAMENTO_COORDS
from infrastructure.route_service import RouteService

API_BASE = "https://gyf-care-backend.onrender.com/api"

route_service = RouteService()


# ================================
# API HELPERS
# ================================
def api_get(path: str, params: dict | None = None):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params)
    if resp.status_code >= 400:
        raise RuntimeError(f"GET {url} → {resp.status_code}: {resp.text}")
    return resp.json()


def api_post(path: str, body: dict):
    url = f"{API_BASE}{path}"
    resp = requests.post(url, json=body)
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {url} → {resp.status_code}: {resp.text}")
    return resp.json()


# ================================
# TOOLTIP HELPERS
# ================================
def _title_paciente(p: dict) -> str:
    pid = p.get("code") or p.get("id")
    dept = p.get("department") or "-"
    disease = p.get("disease") or "-"
    severity = p.get("severity") or "-"
    return "<br>".join(
        [
            f"<b>Paciente {pid}</b>",
            f"Depto: {dept}",
            f"Enfermedad: {disease}",
            f"Gravedad: {severity}",
        ]
    )


def _title_hospital_backend(h: dict) -> str:
    hid = h.get("id") or h.get("code")
    name = h.get("name") or "-"
    dept = h.get("department") or "-"
    specs = h.get("specialties") or "-"
    return "<br>".join(
        [
            f"<b>Hospital {hid}</b>",
            name,
            f"Depto: {dept}",
            f"Especialidades: {specs}",
        ]
    )


# ================================
# PYVIS — GRAFO INTERACTIVO
# ================================
def draw_graph(patients, hospitals, edges, title: str, max_edges: int = 8000):
    net = Network(
        height="800px",
        width="100%",
        bgcolor="#FFFFFF",
        font_color="black",
        notebook=False,
    )
    net.force_atlas_2based(gravity=-50)
    net.heading = title

    base_colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    dept_color_map: dict[str, str] = {}
    hospital_color_map: dict[str, str] = {}

    # Hospitales
    for h in hospitals:
        hid = h.get("id")
        if hid is None:
            continue
        dept = h.get("department") or "Hospital"

        if dept not in dept_color_map:
            dept_color_map[dept] = base_colors[len(dept_color_map) % len(base_colors)]
        color = dept_color_map[dept]
        hospital_color_map[str(hid)] = color

        net.add_node(
            str(hid),
            label=str(hid),
            title=_title_hospital_backend(h),
            color=color,
            shape="square",
            size=22,
            borderWidth=3,
            group=dept,
        )

    # Pacientes
    for p in patients:
        pid = p.get("id")
        if pid is None:
            continue
        net.add_node(
            str(pid),
            label=str(pid),
            title=_title_paciente(p),
            color="#555555",
            shape="dot",
            size=6,
            group="Paciente",
        )

    # Aristas (limitadas)
    total_edges = len(edges)
    if total_edges > max_edges:
        edges_to_draw = random.sample(edges, max_edges)
        st.info(f"Se muestran {max_edges} de {total_edges} aristas.")
    else:
        edges_to_draw = edges

    for e in edges_to_draw:
        s = str(e.get("source"))
        t = str(e.get("target"))
        dist = e.get("weight") or e.get("distance_km") or e.get("dist_km")

        hosp_id = t if t in hospital_color_map else (s if s in hospital_color_map else None)
        edge_color = hospital_color_map.get(hosp_id, "#CCCCCC")

        title_edge: Optional[str] = None
        if dist is not None:
            try:
                title_edge = f"Distancia: {float(dist):.2f} km"
            except Exception:
                title_edge = f"Distancia: {dist}"

        net.add_edge(
            s,
            t,
            color=edge_color,
            width=1,
            title=title_edge,
            physics=True,
        )

    html_str = net.generate_html(notebook=False)
    components.html(html_str, height=800, scrolling=True)


# ================================
# MAIN UI
# ================================
def show_backend_dashboard():
    st.header("Panel backend: grafos, asignación y rutas reales")

    # =========================
    # Cargar pacientes y hospitales DESDE EL BACKEND
    # =========================
    try:
        patients_list = api_get("/patients")
    except Exception as e:
        st.error(f"No se pudo obtener /patients: {e}")
        return

    if not patients_list:
        st.warning("No hay pacientes en el backend.")
        return

    # hospitales opcionales, solo para el mapa
    hospitals_list = []
    try:
        hospitals_list = api_get("/hospitals")
    except Exception:
        hospitals_list = []

    # =========================
    # 1) GRAFO
    # =========================
    st.subheader("1. Grafo")

    mode = st.selectbox(
        "Tipo de grafo",
        options=["bipartite_knn", "knn", "radius"],
        format_func=lambda m: {
            "knn": "KNN geográfico",
            "radius": "Por radio",
            "bipartite_knn": "Bipartito paciente → hospital",
        }[m],
    )

    k = None
    radius_km = None

    if mode in ("knn", "bipartite_knn"):
        k = st.number_input("k (vecinos)", min_value=1, max_value=50, value=10, key="k_vis")

    if mode == "radius":
        radius_km = st.number_input(
            "Radio (km)", min_value=1.0, max_value=500.0, value=50.0, key="r_vis"
        )

    edge_limit = st.slider(
        "Máx. aristas a visualizar",
        min_value=1000,
        max_value=30000,
        value=8000,
        step=1000,
    )

    if st.button("Generar grafo", type="primary"):
        try:
            if mode == "knn":
                data = api_get("/graph/knn", params={"k": int(k)})
                title = f"Grafo KNN (k={k})"
            elif mode == "radius":
                data = api_get("/graph/radius", params={"radius": float(radius_km)})
                title = f"Grafo por radio (R={radius_km} km)"
            else:
                data = api_get("/graph/bipartite", params={"k": int(k)})
                title = f"Grafo bipartito (k={k})"

            patients = data.get("patients", [])
            hospitals = data.get("hospitals", [])
            edges = data.get("edges", [])

            st.success(
                f"Grafo: {len(patients)} pacientes, "
                f"{len(hospitals)} hospitales, {len(edges)} aristas."
            )
            draw_graph(patients, hospitals, edges, title, max_edges=int(edge_limit))
        except Exception as e:
            st.error(f"Error al obtener grafo: {e}")

    st.markdown("---")

    # =========================
    # 2) COMPARACIÓN DE GRAFOS
    # =========================
    st.subheader("2. Comparación de constructores de grafos")

    col1, col2 = st.columns(2)
    k_cmp = col1.number_input(
        "k (KNN y bipartito)", min_value=1, max_value=50, value=10, key="k_cmp"
    )
    radius_cmp = col2.number_input(
        "Radio (km)", min_value=1.0, max_value=500.0, value=50.0, key="r_cmp"
    )

    if st.button("Comparar métodos"):
        try:
            cmp_data = api_get(
                "/graph/compare",
                params={"k": int(k_cmp), "radius": float(radius_cmp)},
            )
            graphs = cmp_data.get("graphs", [])
            if graphs:
                st.dataframe(pd.DataFrame(graphs))
            else:
                st.warning("Sin datos desde /graph/compare.")
        except Exception as e:
            st.error(f"Error /graph/compare: {e}")

    st.markdown("---")

    # =========================
    # 3) ASIGNACIÓN + MAPA
    # =========================
    st.subheader("3. Asignación de paciente y rutas")

    # Paciente desde /patients (backend)
    opciones_pac = [
        f"{p.get('code')} - {p.get('department', 'N/A')} - {p.get('disease', 'N/A')}"
        for p in patients_list
    ]
    codigos_pac = [p.get("code") for p in patients_list]

    seleccion = st.selectbox("Paciente", opciones_pac)
    idx = opciones_pac.index(seleccion)
    selected_code = codigos_pac[idx]
    paciente_sel = patients_list[idx]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ID", paciente_sel.get("code"))
    c2.metric("Gravedad", paciente_sel.get("severity", "N/A"))
    c3.metric("Departamento", paciente_sel.get("department", "N/A"))
    enf = str(paciente_sel.get("disease", "N/A"))
    c4.metric("Enfermedad", enf[:20] + "..." if len(enf) > 20 else enf)

    # Config grafo para backend
    colg1, colg2, colg3 = st.columns(3)
    with colg1:
        assign_graph_mode = st.selectbox(
            "Grafo para asignar",
            options=["bipartite_knn", "knn", "radius"],
            format_func=lambda m: {
                "knn": "KNN geográfico",
                "radius": "Por radio",
                "bipartite_knn": "Bipartito paciente → hospital",
            }[m],
        )
    with colg2:
        if assign_graph_mode in ("knn", "bipartite_knn"):
            k_assign = st.number_input(
                "k asignación", min_value=1, max_value=50, value=10, key="k_assign"
            )
        else:
            k_assign = None
    with colg3:
        if assign_graph_mode == "radius":
            radius_assign = st.number_input(
                "Radio asignación (km)",
                min_value=1.0,
                max_value=500.0,
                value=50.0,
                key="r_assign",
            )
        else:
            radius_assign = None

    colA, colB = st.columns(2)

    # -------- 3.1 Asignación (backend) ----------
    with colA:
        st.markdown("##### Asignación backend")
        if st.button("Asignar paciente con este grafo", key="btn_best"):
            try:
                k_val = int(k_assign) if k_assign is not None else 10
                radius_val = float(radius_assign) if radius_assign is not None else 50.0

                body = {
                    "patient_code": selected_code,
                    "graph_mode": assign_graph_mode,
                    "k": k_val,
                    "radius_km": radius_val,
                }

                best = api_post("/assign/patient-best", body)

                patient_json = best.get("patient", {})
                hospital_json = best.get("hospital", {})
                algo = best.get("algorithm_used")
                dist_geo = best.get("distance_geo_km")
                paths = best.get("paths") or {}

                # Ruta real con RouteService (ORS)
                p_lat = patient_json.get("lat")
                p_lon = patient_json.get("lon")
                h_lat = hospital_json.get("lat")
                h_lon = hospital_json.get("lon")

                ruta = None
                if None not in (p_lat, p_lon, h_lat, h_lon):
                    ruta = route_service.get_route(
                        start_lat=float(p_lat),
                        start_lon=float(p_lon),
                        end_lat=float(h_lat),
                        end_lon=float(h_lon),
                    )

                st.session_state["backend_assign_result"] = {
                    "patient_code": selected_code,
                    "patient_json": patient_json,
                    "hospital_json": hospital_json,
                    "algo": algo,
                    "dist_geo": dist_geo,
                    "paths": paths,
                    "route": ruta,
                }

                st.success("Asignación calculada correctamente.")

            except Exception as e:
                st.error(f"Error /assign/patient-best: {e}")

    # -------- 3.2 Comparación de algoritmos ----------
    with colB:
        st.markdown("##### Comparación de algoritmos")
        if st.button("Comparar algoritmos con este grafo", key="btn_compare"):
            try:
                k_val = int(k_assign) if k_assign is not None else 10
                radius_val = float(radius_assign) if radius_assign is not None else 50.0

                body = {
                    "patient_code": selected_code,
                    "graph_mode": assign_graph_mode,
                    "k": k_val,
                    "radius_km": radius_val,
                }

                cmp = api_post("/assign/compare-patient", body)
                algos = cmp.get("assignment_algorithms", [])

                if algos:
                    df = pd.DataFrame(algos)
                    cols_basic = [
                        c
                        for c in ["name", "big_o", "time_ms", "distance_geo_km"]
                        if c in df.columns
                    ]
                    if cols_basic:
                        st.dataframe(
                            df[cols_basic].style.format(
                                {
                                    "time_ms": "{:.6f}",
                                    "distance_geo_km": "{:.2f}",
                                }
                            )
                        )

                    paths_rows = []
                    for a in algos:
                        aname = a.get("name")
                        pth = a.get("paths") or {}
                        d = pth.get("dijkstra") or {}
                        b = pth.get("bellman_ford") or {}

                        if d:
                            paths_rows.append(
                                {
                                    "assignment_algo": aname,
                                    "route_algo": d.get("algorithm", "Dijkstra"),
                                    "distance": d.get("distance"),
                                    "time_ms": d.get("time_ms"),
                                }
                            )
                        if b:
                            paths_rows.append(
                                {
                                    "assignment_algo": aname,
                                    "route_algo": b.get("algorithm", "Bellman-Ford"),
                                    "distance": b.get("distance"),
                                    "time_ms": b.get("time_ms"),
                                }
                            )

                    if paths_rows:
                        df_paths = pd.DataFrame(paths_rows)
                        st.dataframe(
                            df_paths.style.format(
                                {"time_ms": "{:.6f}", "distance": "{:.4f}"}
                            )
                        )
                else:
                    st.warning("Sin datos de algoritmos desde /assign/compare-patient.")
            except Exception as e:
                st.error(f"Error /assign/compare-patient: {e}")

    # ----- Mostrar último resultado de asignación (persistente) -----
    assign_state = st.session_state.get("backend_assign_result")
    if assign_state and assign_state.get("patient_code") == selected_code:
        patient_json = assign_state.get("patient_json", {})
        hospital_json = assign_state.get("hospital_json", {})
        algo = assign_state.get("algo")
        dist_geo = assign_state.get("dist_geo")
        paths = assign_state.get("paths") or {}
        ruta = assign_state.get("route")

        st.markdown("#### Detalle de la asignación seleccionada")

        st.write(
            f"**Paciente:** {patient_json.get('code')} — "
            f"{patient_json.get('department')} — {patient_json.get('disease')}"
        )
        st.write(
            f"**Hospital:** {hospital_json.get('name')} "
            f"(`{hospital_json.get('code')}`) — {hospital_json.get('department')}"
        )

        dijkstra = paths.get("dijkstra") or {}
        bellman = paths.get("bellman_ford") or {}

        td = dijkstra.get("time_ms")
        tb = bellman.get("time_ms")

        c_alg, c_dist, c_dij, c_bf = st.columns(4)
        c_alg.metric("Algoritmo de asignación", algo or "-")

        if dist_geo is not None:
            try:
                c_dist.metric("Distancia geo", f"{float(dist_geo):.2f} km")
            except Exception:
                c_dist.metric("Distancia geo", str(dist_geo))

        if td is not None:
            try:
                c_dij.metric("Dijkstra (ms)", f"{float(td):.3f}")
            except Exception:
                c_dij.metric("Dijkstra (ms)", str(td))

        if tb is not None:
            try:
                c_bf.metric("Bellman-Ford (ms)", f"{float(tb):.3f}")
            except Exception:
                c_bf.metric("Bellman-Ford (ms)", str(tb))

        # Mensaje amigable si no hay carretera cerca
        if ruta and not ruta.get("success"):
            details = str(ruta.get("details", ""))
            if "Could not find routable point" in details:
                st.warning(
                    "No se encontró una **carretera cercana** al paciente u hospital "
                    "(zona sin vías registradas en el mapa). "
                    "Se muestra solo la línea recta estimada."
                )
            else:
                st.warning(
                    f"No se pudo trazar la ruta real: {ruta.get('error', 'Error desconocido')}"
                )

    # =========================
    # 4) MAPA — SIEMPRE VISIBLE
    # =========================
    st.markdown("#### Mapa paciente → hospital")

    # Centro del mapa: paciente seleccionado
    p_lat = paciente_sel.get("lat")
    p_lon = paciente_sel.get("lon")
    if None not in (p_lat, p_lon):
        center_coords = [float(p_lat), float(p_lon)]
        zoom_start = 8
    else:
        dept = paciente_sel.get("department", "Lima")
        center_coords = DEPARTAMENTO_COORDS.get(dept, [-12.0464, -77.0428])
        zoom_start = 6

    m = folium.Map(location=center_coords, zoom_start=zoom_start)

    # Dibujar hospitales del backend (si hay /hospitals)
    for h in hospitals_list:
        hlat = h.get("lat")
        hlon = h.get("lon")
        if None in (hlat, hlon):
            continue
        popup_html = _title_hospital_backend(h)
        folium.CircleMarker(
            location=[float(hlat), float(hlon)],
            radius=7,
            color="blue",
            fill=True,
            fill_color="blue",
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

    # Paciente seleccionado (en rojo)
    if None not in (p_lat, p_lon):
        folium.Marker(
            location=[float(p_lat), float(p_lon)],
            popup=_title_paciente(paciente_sel),
            icon=folium.Icon(color="red", icon="user"),
        ).add_to(m)

    # Dibujar hospital asignado + ruta si hay resultado
    if assign_state and assign_state.get("patient_code") == selected_code:
        hospital_json = assign_state.get("hospital_json") or {}
        ruta = assign_state.get("route")

        h_lat = hospital_json.get("lat")
        h_lon = hospital_json.get("lon")

        if None not in (h_lat, h_lon):
            folium.Marker(
                location=[float(h_lat), float(h_lon)],
                popup=_title_hospital_backend(hospital_json),
                icon=folium.Icon(color="green", icon="plus-sign"),
            ).add_to(m)

        if ruta and ruta.get("success"):
            # ruta["geometry"] viene en [[lon, lat], ...]
            coords_folium = [[lat, lon] for lon, lat in ruta["geometry"]]
            folium.PolyLine(
                locations=coords_folium,
                color="green",
                weight=4,
                opacity=0.8,
                tooltip=f"Ruta real: {ruta['distance']:.2f} km, {ruta['duration']:.0f} min",
            ).add_to(m)
        elif ruta is not None and None not in (p_lat, p_lon, h_lat, h_lon):
            folium.PolyLine(
                locations=[
                    [float(p_lat), float(p_lon)],
                    [float(h_lat), float(h_lon)],
                ],
                color="gray",
                weight=3,
                opacity=0.6,
                dash_array="10",
                tooltip="Línea recta (ruta real no disponible)",
            ).add_to(m)

    st_folium(m, width=MAP_WIDTH, height=MAP_HEIGHT, key="map_backend_main")
