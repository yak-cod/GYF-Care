# presentation/ui_backend_dashboard.py

import random

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from pyvis.network import Network

import folium
from streamlit_folium import st_folium

API_BASE = "http://localhost:5000/api"


# ================================
# API WRAPPERS
# ================================

def api_get(path: str, params: dict | None = None):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict):
    url = f"{API_BASE}{path}"
    resp = requests.post(url, json=body)
    resp.raise_for_status()
    return resp.json()


# ================================
# HELPERS PARA TOOLTIP
# ================================

def _title_paciente(p: dict) -> str:
    pid = p.get("code") or p.get("id")
    dept = p.get("department") or p.get("departamento") or "-"
    disease = p.get("disease") or p.get("enfermedad") or "-"
    severity = p.get("severity") or p.get("gravedad") or "-"
    lines = [
        f"<b>Paciente {pid}</b>",
        f"Depto: {dept}",
        f"Enfermedad: {disease}",
        f"Gravedad: {severity}",
    ]
    return "<br>".join(lines)


def _title_hospital(h: dict) -> str:
    hid = h.get("id")
    name = h.get("name") or h.get("nombre") or "-"
    dept = h.get("department") or h.get("departamento") or "-"
    beds = (
        h.get("beds")
        or h.get("capacidad_camas")
        or h.get("Capacidad_Camas")
        or h.get("capacity")
        or "-"
    )
    uci = h.get("uci_beds") or h.get("camas_uci") or h.get("Camas_UCI") or "-"
    specs = h.get("specialties") or h.get("especialidades") or "-"
    lines = [
        f"<b>Hospital {hid}</b>",
        name,
        f"Depto: {dept}",
        f"Camas: {beds} | UCI: {uci}",
        f"Especialidades: {specs}",
    ]
    return "<br>".join(lines)


# ================================
# PYVIS — GRAFO INTERACTIVO
# ================================

def draw_graph(patients, hospitals, edges, title: str, max_edges: int = 8000):
    """
    Dibuja un grafo interactivo usando PyVis.
    - Pacientes: nodos grises pequeños.
    - Hospitales: nodos de color (por departamento) más grandes.
    - Aristas: color del hospital al que conectan.
    - max_edges: máximo de aristas a visualizar (para no saturar la vista).
    """

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#FFFFFF",
        font_color="black",
        notebook=False,
    )
    net.force_atlas_2based(gravity=-50)
    net.heading = title

    # Colores por departamento de hospital
    base_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf",
    ]
    dept_color_map: dict[str, str] = {}
    hospital_color_map: dict[str, str] = {}

    # Hospitales
    for h in hospitals:
        hid = h.get("id")
        dept = h.get("department") or h.get("departamento") or "Hospital"

        if dept not in dept_color_map:
            dept_color_map[dept] = base_colors[len(dept_color_map) % len(base_colors)]
        color = dept_color_map[dept]
        hospital_color_map[hid] = color

        net.add_node(
            hid,
            label=str(hid),
            title=_title_hospital(h),
            color=color,
            shape="square",
            size=22,
            borderWidth=3,
            group=dept,
        )

    # Pacientes
    for p in patients:
        pid = p.get("id")
        net.add_node(
            pid,
            label=str(pid),
            title=_title_paciente(p),
            color="#555555",
            shape="dot",
            size=6,
            group="Paciente",
        )

    # Limitar número de aristas para visualización
    total_edges = len(edges)
    if total_edges > max_edges:
        edges_to_draw = random.sample(edges, max_edges)
        st.info(
            f"Se muestran {max_edges} de {total_edges} aristas para una mejor visualización."
        )
    else:
        edges_to_draw = edges

    # Aristas
    for e in edges_to_draw:
        s = e.get("source")
        t = e.get("target")
        dist = e.get("weight") or e.get("distance_km") or e.get("dist_km")

        # color = color del hospital si está en el grafo
        hosp_id = t if t in hospital_color_map else (s if s in hospital_color_map else None)
        edge_color = hospital_color_map.get(hosp_id, "#CCCCCC")

        title_edge = None
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

    # Generar HTML en memoria
    html_str = net.generate_html(notebook=False)
    components.html(html_str, height=800, scrolling=True)

    st.caption(
        "Pacientes = gris • Hospitales = colores por departamento • "
        "Aristas = color del hospital (usa zoom/drag y hover para detalles)."
    )


# ================================
# MAIN UI
# ================================

def show_backend_dashboard():
    st.title("Panel de algoritmos y grafos (Backend Flask)")

    st.markdown("""
        ### Funcionalidades:
        - Visualizar grafos **KNN**, **Radio** y **Bipartito**.
        - Ver métricas de construcción de grafo.
        - Elegir un **paciente** y un **grafo** para la asignación.
        - Comparar algoritmos de **asignación**: Greedy, Hungarian, MCMF.
        - Ver tiempos de los algoritmos de **ruta más corta**: Dijkstra y Bellman-Ford.
    """)

    # ================================
    # 1) GRAFOS
    # ================================
    st.header("1. Selección y visualización de grafo")

    st.caption(
        "Aquí eliges **cómo se construye el grafo** que conecta pacientes con hospitales.\n"
        "- KNN: cada nodo se conecta con sus k vecinos más cercanos.\n"
        "- Bipartito: cada paciente se conecta con sus k hospitales más cercanos.\n"
        "- Radio: se conectan nodos que están a una distancia menor o igual al radio en km."
    )

    mode = st.selectbox(
        "Tipo de grafo para visualizar",
        options=["bipartite_knn", "knn", "radius"],
        format_func=lambda m: {
            "knn": "KNN geográfico",
            "radius": "Por radio (ε-vecindario)",
            "bipartite_knn": "Bipartito paciente → hospital",
        }[m],
    )

    k = None
    radius_km = None

    if mode in ("knn", "bipartite_knn"):
        k = st.number_input(
            "Parámetro k (número de vecinos más cercanos)",
            min_value=1,
            max_value=50,
            value=10,
            key="k_vis",
            help=(
                "k indica cuántos vecinos se conectan:\n"
                "- En KNN: cada nodo se conecta con sus k nodos más cercanos.\n"
                "- En Bipartito: cada paciente se conecta con sus k hospitales más cercanos."
            ),
        )

    if mode == "radius":
        radius_km = st.number_input(
            "Radio (km) del grafo por radio",
            min_value=1.0,
            max_value=500.0,
            value=50.0,
            key="r_vis",
            help=(
                "Dos nodos se conectan si la distancia entre ellos "
                "es menor o igual a este valor (en kilómetros)."
            ),
        )

    # Slider para controlar cuántas aristas se dibujan
    edge_limit = st.slider(
        "Máximo de aristas a visualizar",
        min_value=1000,
        max_value=30000,
        value=8000,
        step=1000,
        help="Solo se dibujan hasta este número de aristas para que el grafo sea legible.",
    )

    if st.button("Generar grafo", type="primary"):
        if mode == "knn":
            data = api_get("/graph/knn", params={"k": int(k)})
            title = f"Grafo KNN (k={k})"
        elif mode == "radius":
            data = api_get("/graph/radius", params={"radius": float(radius_km)})
            title = f"Grafo por radio R={radius_km} km"
        else:  # bipartito
            data = api_get("/graph/bipartite", params={"k": int(k)})
            title = f"Grafo bipartito paciente → hospital (k={k})"

        patients = data.get("patients", [])
        hospitals = data.get("hospitals", [])
        edges = data.get("edges", [])

        st.success(
            f"Grafo generado: {len(patients)} pacientes, "
            f"{len(hospitals)} hospitales, {len(edges)} aristas."
        )
        draw_graph(patients, hospitals, edges, title, max_edges=int(edge_limit))

    # ================================
    # 2) COMPARACIÓN DE GRAFOS
    # ================================
    st.subheader("Comparación de constructores de grafos")

    st.caption(
        "En esta sección comparas los **tres métodos de construcción de grafos** usando los mismos parámetros.\n"
        "- `k para comparar KNN y Bipartito`: cuántos vecinos se conectan por nodo/paciente.\n"
        "- `Radio (km) para comparar por radio`: distancia máxima para conectar nodos.\n"
        "Las métricas devueltas indican qué método es más rápido y cuál genera un grafo más denso."
    )

    col1, col2 = st.columns(2)
    k_cmp = col1.number_input(
        "k para comparar KNN y Bipartito",
        min_value=1,
        max_value=50,
        value=10,
        key="k_cmp",
        help="Este k se usa tanto en el grafo KNN como en el grafo bipartito.",
    )
    radius_cmp = col2.number_input(
        "Radio (km) para comparar grafo por radio",
        min_value=1.0,
        max_value=500.0,
        value=50.0,
        key="r_cmp",
        help="Este radio se usa para construir el grafo basado en distancia.",
    )

    if st.button("Comparar métodos"):
        cmp_data = api_get(
            "/graph/compare",
            params={"k": int(k_cmp), "radius": float(radius_cmp)},
        )
        graphs = cmp_data.get("graphs", [])
        if graphs:
            st.dataframe(pd.DataFrame(graphs))
            st.markdown("""
            - `time_ms`: tiempo que tomó construir cada grafo.
            - `num_edges`: número total de aristas del grafo.
            - `avg_degree`: grado promedio, indica qué tan denso es el grafo.
            """)
        else:
            st.warning("No se recibieron datos.")

    st.markdown("---")

    # ================================
    # 3) ASIGNACIÓN DE PACIENTES
    # ================================
    st.header("2. Asignación de pacientes")

    # --- Configuración de grafo para la ASIGNACIÓN ---
    st.subheader("Configurar grafo para la asignación")

    st.caption(
        "Aquí eliges **qué grafo** usará el backend para calcular la asignación del paciente.\n"
        "Usará los mismos constructores de grafos, pero ahora aplicados al cálculo de rutas y hospital final."
    )

    colg1, colg2, colg3 = st.columns(3)
    with colg1:
        assign_graph_mode = st.selectbox(
            "Grafo para asignar",
            options=["bipartite_knn", "knn", "radius"],
            format_func=lambda m: {
                "knn": "KNN geográfico",
                "radius": "Por radio (ε-vecindario)",
                "bipartite_knn": "Bipartito paciente → hospital",
            }[m],
        )

    with colg2:
        if assign_graph_mode in ("knn", "bipartite_knn"):
            k_assign = st.number_input(
                "k (asignación: vecinos/hospitales más cercanos)",
                min_value=1,
                max_value=50,
                value=10,
                key="k_assign",
                help="En asignación, k controla cuántos vecinos/hospitales cercanos se consideran en el grafo.",
            )
        else:
            k_assign = None

    with colg3:
        if assign_graph_mode == "radius":
            radius_assign = st.number_input(
                "Radio (km) para el grafo de asignación",
                min_value=1.0,
                max_value=500.0,
                value=50.0,
                key="r_assign",
                help="En asignación, el grafo conecta nodos que estén dentro de este radio en km.",
            )
        else:
            radius_assign = None

    st.caption(
        "El grafo elegido aquí será el que use el backend para calcular rutas y asignar el hospital."
    )

    # --- Lista de pacientes ---
    try:
        patients_list = api_get("/patients")
    except Exception as e:
        st.error(f"No se pudo obtener /patients: {e}")
        return

    if not patients_list:
        st.warning("No hay pacientes disponibles.")
        return

    options = [
        f"{p.get('code')} - {p.get('department')} - {p.get('disease')}"
        for p in patients_list
    ]
    codes = [p.get("code") for p in patients_list]

    selected = st.selectbox("Selecciona un paciente", options)
    selected_code = codes[options.index(selected)]

    # Inicializar estado para guardar último resultado de asignación
    if "best_assignment_state" not in st.session_state:
        st.session_state["best_assignment_state"] = None

    # ================================
    # 3.1 ASIGNACIÓN FINAL
    # ================================
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Asignación final (patient-best)")

        if st.button("Asignar paciente con este grafo", key="btn_best"):
            try:
                body = {
                    "patient_code": selected_code,
                    "graph_mode": assign_graph_mode,
                    "k": int(k_assign) if k_assign is not None else None,
                    "radius_km": float(radius_assign) if radius_assign is not None else None,
                }
                best = api_post("/assign/patient-best", body)

                # Guardar en session_state para que NO desaparezca
                st.session_state["best_assignment_state"] = {
                    "best": best,
                    "graph_mode": assign_graph_mode,
                    "k_assign": k_assign,
                    "radius_assign": radius_assign,
                }
            except Exception as e:
                st.error(f"Error /assign/patient-best: {e}")

        state = st.session_state.get("best_assignment_state")

        if state:
            best = state["best"]
            g_mode = state["graph_mode"]
            k_a = state["k_assign"]
            r_a = state["radius_assign"]

            patient = best.get("patient", {})
            hospital = best.get("hospital", {})
            algo = best.get("algorithm_used")
            dist_geo = best.get("distance_geo_km")
            paths = best.get("paths") or {}

            st.markdown("#### Paciente")
            st.write(
                f"**{patient.get('code')}** — {patient.get('department')} — "
                f"{patient.get('disease')} (Gravedad: {patient.get('severity')})"
            )

            st.markdown("#### Hospital asignado")
            st.write(
                f"**{hospital.get('name')}** (`{hospital.get('code')}`) — "
                f"{hospital.get('department')}"
            )

            st.markdown("#### Métricas de la asignación")
            colm1, colm2, colm3 = st.columns(3)
            colm1.metric("Algoritmo usado", algo)

            if dist_geo is not None:
                try:
                    colm2.metric("Distancia geo (km)", f"{float(dist_geo):.2f}")
                except Exception:
                    colm2.metric("Distancia geo (km)", str(dist_geo))

            dijkstra = paths.get("dijkstra") or {}
            bellman = paths.get("bellman_ford") or {}

            td = dijkstra.get("time_ms")
            tb = bellman.get("time_ms")

            # Métrica solo con el título y detalle abajo para no cortar texto
            colm3.metric("Tiempos rutas (ms)", "")

            if td is not None or tb is not None:
                parts = []
                if td is not None:
                    try:
                        parts.append(f"Dijkstra: **{float(td):.3f} ms**")
                    except Exception:
                        parts.append(f"Dijkstra: **{td} ms**")
                if tb is not None:
                    try:
                        parts.append(f"Bellman-Ford: **{float(tb):.3f} ms**")
                    except Exception:
                        parts.append(f"Bellman-Ford: **{tb} ms**")

                st.caption(" | ".join(parts))

            st.caption(
                "Dijkstra y Bellman-Ford se usan como algoritmos de ruta más corta "
                "para medir las distancias en el grafo entre paciente y hospital asignado."
            )

            # Grafo configurado
            st.markdown("##### Grafo usado en la asignación")
            st.markdown(f"- **Tipo:** `{g_mode}`")
            if k_a is not None:
                st.markdown(f"- **k:** `{int(k_a)}`")
            if r_a is not None:
                st.markdown(f"- **Radio (km):** `{float(r_a)}`")

            # ============================
            # Mapa Folium paciente → hospital
            # ============================
            p_lat = patient.get("lat")
            p_lon = patient.get("lon")
            h_lat = hospital.get("lat")
            h_lon = hospital.get("lon")

            if None not in (p_lat, p_lon, h_lat, h_lon):
                st.markdown("##### Ruta en el mapa")

                center_lat = (p_lat + h_lat) / 2
                center_lon = (p_lon + h_lon) / 2

                m = folium.Map(location=[center_lat, center_lon], zoom_start=7)

                folium.Marker(
                    [p_lat, p_lon],
                    popup=f"Paciente {patient.get('code')}",
                    tooltip="Paciente",
                    icon=folium.Icon(color="red", icon="user"),
                ).add_to(m)

                folium.Marker(
                    [h_lat, h_lon],
                    popup=f"Hospital {hospital.get('name')} ({hospital.get('code')})",
                    tooltip="Hospital asignado",
                    icon=folium.Icon(color="green", icon="plus-sign"),
                ).add_to(m)

                folium.PolyLine(
                    locations=[[p_lat, p_lon], [h_lat, h_lon]],
                    weight=4,
                    opacity=0.8,
                ).add_to(m)

                st_folium(m, width=900, height=500)
            else:
                st.info("No se encontraron coordenadas para mostrar el mapa.")

    # ================================
    # 3.2 COMPARACIÓN DE ALGORITMOS
    # ================================
    with colB:
        st.subheader("Comparación de algoritmos (asignación y rutas)")
        if st.button("Comparar algoritmos con este grafo", key="btn_compare"):
            try:
                body = {
                    "patient_code": selected_code,
                    "graph_mode": assign_graph_mode,
                    "k": int(k_assign) if k_assign is not None else None,
                    "radius_km": float(radius_assign) if radius_assign is not None else None,
                }
                cmp = api_post("/assign/compare-patient", body)
                algos = cmp.get("assignment_algorithms", [])

                if algos:
                    df = pd.DataFrame(algos)

                    # Tabla de métricas principales de asignación
                    cols_basic = [
                        c for c in ["name", "big_o", "time_ms", "distance_geo_km"]
                        if c in df.columns
                    ]
                    if cols_basic:
                        st.markdown("##### Algoritmos de asignación (Greedy / Hungarian / MCMF)")
                        st.dataframe(
                            df[cols_basic].style.format(
                                {
                                    "time_ms": "{:.6f}",
                                    "distance_geo_km": "{:.2f}",
                                }
                            )
                        )
                        st.caption(
                            "`time_ms` muestra el tiempo de ejecución de cada algoritmo de asignación; "
                            "`distance_geo_km` la distancia geográfica paciente–hospital asignado."
                        )

                    # Comparación de algoritmos de ruta más corta por cada algoritmo de asignación
                    paths_rows = []
                    for a in algos:
                        aname = a.get("name")
                        p = a.get("paths") or {}
                        d = p.get("dijkstra") or {}
                        b = p.get("bellman_ford") or {}

                        if d:
                            paths_rows.append({
                                "assignment_algo": aname,
                                "route_algo": d.get("algorithm", "Dijkstra"),
                                "distance": d.get("distance"),
                                "time_ms": d.get("time_ms"),
                            })
                        if b:
                            paths_rows.append({
                                "assignment_algo": aname,
                                "route_algo": b.get("algorithm", "Bellman-Ford"),
                                "distance": b.get("distance"),
                                "time_ms": b.get("time_ms"),
                            })

                    if paths_rows:
                        df_paths = pd.DataFrame(paths_rows)
                        st.markdown("##### Algoritmos de ruta más corta (Dijkstra vs Bellman-Ford)")
                        st.dataframe(
                            df_paths.style.format(
                                {
                                    "time_ms": "{:.6f}",
                                    "distance": "{:.4f}",
                                }
                            )
                        )
                        st.caption(
                            "Aquí se comparan los tiempos y distancias de Dijkstra y Bellman-Ford, "
                            "usados como algoritmos de ruta más corta sobre el grafo configurado."
                        )

                    # Detalle completo, sin columnas grandes
                    st.expander("Ver detalle completo de asignación (sin hospital/paths)").dataframe(
                        df.drop(columns=["hospital", "paths"], errors="ignore")
                    )
                else:
                    st.warning("Sin datos de algoritmos de asignación.")
            except Exception as e:
                st.error(f"Error /assign/compare-patient: {e}")
