import pandas as pd
import streamlit as st
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

st.set_page_config(page_title="Observatorio Laboral Regional - MVP", layout="wide")

# Estado de navegación desde el Home
if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "HOME"

# Barra superior de navegación rápida
col_nav1, col_nav2, col_nav3, col_nav4 = st.columns(4)
with col_nav1:
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.vista_actual = "HOME"
with col_nav2:
    if st.button("🏳️ Vista por País", use_container_width=True):
        st.session_state.vista_actual = "PAIS"
with col_nav3:
    if st.button("📋 Ficha de Ocupación", use_container_width=True):
        st.session_state.vista_actual = "FICHA"
with col_nav4:
    if st.button("🌎 Macro Regional (3 Países)", use_container_width=True):
        st.session_state.vista_actual = "REGIONAL"

st.divider()

# =====================================================================
# PANTALLA INICIAL: HOME
# =====================================================================
if st.session_state.vista_actual == "HOME":
    st.title("🏠 Home — Sistema de Visualización Regional y Ocupaciones")
    st.markdown("Selecciona el flujo de análisis que deseas consultar:")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("1. Home ➔ PAÍS")
        st.write("Dashboard con visualización general del país seleccionado (Argentina, Chile o Uruguay).")
        if st.button("Ir al Dashboard por País ➔", key="btn_home_pais", use_container_width=True):
            st.session_state.vista_actual = "PAIS"
            st.rerun()

    with c2:
        st.subheader("2. Home ➔ PAÍS + Sector + Área + Fechas")
        st.write("Ficha completa de la ocupación con comparativas sectoriales/regionales y trazabilidad por fechas.")
        if st.button("Ir a Ficha de Ocupación ➔", key="btn_home_ficha", use_container_width=True):
            st.session_state.vista_actual = "FICHA"
            st.rerun()

    with c3:
        st.subheader("3. Home ➔ Regional")
        st.write("Vista Macro comparativa con los 3 países del alcance (ARG + CHL + URY).")
        if st.button("Ir a Macro Regional ➔", key="btn_home_reg", use_container_width=True):
            st.session_state.vista_actual = "REGIONAL"
            st.rerun()


# =====================================================================
# RUTA 1: Home --> PAIS --> Dashboard General del País Seleccionado
# =====================================================================
elif st.session_state.vista_actual == "PAIS":
    opciones = client.get("/api/v1/filtros/opciones").json()
    paises_dict = {f"{p['nombre']} ({p['codigo']})": p["codigo"] for p in opciones["paises"]}

    st.sidebar.header("Filtro de País")
    pais_label = st.sidebar.selectbox("Selecciona un País:", list(paises_dict.keys()))
    pais_code = paises_dict[pais_label]

    data = client.get(f"/api/v1/visualizacion/pais/{pais_code}").json()

    st.caption(f"📍 Ruta: **{data['navigation_path']}**")
    st.title(f"Dashboard General — {data['pais_nombre']} ({data['pais_codigo_iso3']})")

    kpis = data["kpis_generales"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ocupaciones en Catálogo", kpis["total_ocupaciones_catalogo"])
    k2.metric("Registros en Consolidado", kpis["total_registros_consolidado"])
    k3.metric("Sectores Cubiertos", kpis["total_sectores"])
    k4.metric(
        "Observados / Proyectados",
        f"{kpis['distribucion_data_type']['observed']} / {kpis['distribucion_data_type']['projected']}",
    )

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Promedio por Sector en el Catálogo")
        df_sec = pd.DataFrame(data["resumen_por_sector"])
        st.bar_chart(df_sec.set_index("sector")["promedio_indicador_catalogo"])
        st.dataframe(df_sec, use_container_width=True, hide_index=True)

    with col_g2:
        st.subheader("Indicadores Promedio del Consolidado Nacional")
        df_met = pd.DataFrame(
            [{"Métrica": k, "Valor Promedio": v} for k, v in kpis["promedios_metricas"].items()]
        )
        st.bar_chart(df_met.set_index("Métrica")["Valor Promedio"])
        st.dataframe(df_met, use_container_width=True, hide_index=True)

    st.subheader(f"Catálogo de 20 Ocupaciones en {data['pais_nombre']}")
    df_occ = pd.DataFrame(data["ocupaciones_pais"])[
        ["ocupacion_uid", "ocupacion_id", "nombre_ocupacion", "ciuo_08", "sector", "area", "metric_value", "data_type", "fuente_oficial"]
    ]
    st.dataframe(df_occ, use_container_width=True, hide_index=True)


# =====================================================================
# RUTA 2: Home --> PAIS + Sector + Area + Fechas --> Ficha de Ocupación
# =====================================================================
elif st.session_state.vista_actual == "FICHA":
    st.sidebar.header("Filtros de la Ficha")
    base_opts = client.get("/api/v1/filtros/opciones").json()

    paises_dict = {f"{p['nombre']} ({p['codigo']})": p["codigo"] for p in base_opts["paises"]}
    pais_label = st.sidebar.selectbox("1. País:", list(paises_dict.keys()))
    pais_sel = paises_dict[pais_label]

    sector_sel = st.sidebar.selectbox("2. Sector:", base_opts["sectores"])

    # Cargar áreas en cascada según el sector elegido
    cascada_opts = client.get("/api/v1/filtros/opciones", params={"pais": pais_sel, "sector": sector_sel}).json()
    area_sel = st.sidebar.selectbox("3. Área:", cascada_opts["areas"])

    fechas_disp = base_opts["fechas_periodos"]
    fecha_desde, fecha_hasta = st.sidebar.select_slider(
        "4. Rango de Fechas (Período):",
        options=fechas_disp,
        value=(fechas_disp[0], fechas_disp[-1]),
    )

    resp = client.get(
        "/api/v1/visualizacion/ficha-ocupacion",
        params={
            "pais": pais_sel,
            "sector": sector_sel,
            "area": area_sel,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    ).json()

    ficha = resp["ficha_ocupacion"]
    comp = resp["comparativas"]

    st.caption(f"📍 Ruta: **{resp['navigation_path']}**")
    st.title(f"📋 Ficha de Ocupación: {ficha['nombre_ocupacion']}")

    # Tarjetas de identificación y trazabilidad (API-003, API-012, API-013)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Clave Única (ISO3 + ID)", ficha["ocupacion_uid"])
    m2.metric("Código CIUO-08", ficha["ciuo_08"])
    m3.metric("Valor Indicador", ficha["valor_actual_catalogo"], delta=f"{comp['vs_sector_nacional']['diferencia']} vs Sector")
    m4.metric("Tipo de Dato", ficha["trazabilidad"]["data_type"])
    m5.metric("Fuente Oficial", ficha["trazabilidad"]["fuente_oficial"])

    st.info(
        f"**Trazabilidad del dato:** Fuente `{ficha['trazabilidad']['fuente_oficial']}` | "
        f"Fecha de extracción: `{ficha['trazabilidad']['fecha_extraccion']}` | "
        f"Sector: `{ficha['sector']}` | Área: `{ficha['area']}`"
    )

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.subheader("Comparativa Regional (ARG vs CHL vs URY)")
        df_reg_comp = pd.DataFrame(comp["vs_otros_paises_region"])
        st.bar_chart(df_reg_comp.set_index("pais_nombre")["metric_value"])
        st.dataframe(df_reg_comp, use_container_width=True, hide_index=True)

    with col_c2:
        st.subheader("Comparativa contra Promedio del Sector Nacional")
        df_sec_comp = pd.DataFrame(
            [
                {"Referencia": ficha["nombre_ocupacion"], "Valor": comp["vs_sector_nacional"]["valor_ocupacion"]},
                {"Referencia": f"Promedio Sector {ficha['sector']} ({pais_sel})", "Valor": comp["vs_sector_nacional"]["promedio_sector"]},
            ]
        )
        st.bar_chart(df_sec_comp.set_index("Referencia")["Valor"])
        st.dataframe(df_sec_comp, use_container_width=True, hide_index=True)

    st.subheader(f"Datos Obtenidos en el Rango de Fechas ({fecha_desde} - {fecha_hasta})")
    df_fechas = pd.DataFrame(resp["datos_en_fechas"])
    st.dataframe(df_fechas, use_container_width=True, hide_index=True)


# =====================================================================
# RUTA 3: Home --> Regional --> Macro con los 3 Países
# =====================================================================
elif st.session_state.vista_actual == "REGIONAL":
    st.sidebar.header("Filtros Macro Regionales")
    periodo_filtro = st.sidebar.selectbox("Filtrar por Período:", ["Todos", "2024", "2025", "2026"])
    params = {} if periodo_filtro == "Todos" else {"period": periodo_filtro}

    reg_data = client.get("/api/v1/visualizacion/regional", params=params).json()

    st.caption(f"📍 Ruta: **{reg_data['navigation_path']}**")
    st.title("🌎 Dashboard Macro Regional — Argentina, Chile y Uruguay")

    cob = reg_data["cobertura_global"]
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Países en Alcance", "ARG + CHL + URY (3)")
    r2.metric("Consolidado Regional Total", f"{cob['total_registros_consolidado']} registros")
    r3.metric("Catálogo Ocupaciones Regional", f"{cob['total_registros_catalogo_ocupaciones']} registros")
    r4.metric("Ocupaciones Únicas MVP", cob["ocupaciones_unicas_mvp"])

    st.subheader("Resumen Macroeconómico por País")
    filas_paises = []
    for item in reg_data["macro_por_pais"]:
        filas_paises.append(
            {
                "Código ISO3": item["pais_codigo_iso3"],
                "País": item["pais_nombre"],
                "Registros Consolidado": item["registros_consolidado"],
                "Ocupaciones Catálogo": item["ocupaciones_catalogo"],
                "Promedio Catálogo": item["promedio_catalogo_ocupaciones"],
                **item["promedios_consolidado"],
            }
        )
    df_macro_paises = pd.DataFrame(filas_paises)
    st.dataframe(df_macro_paises, use_container_width=True, hide_index=True)

    st.subheader("Matriz Comparativa por Sector entre los 3 Países (ARG, CHL, URY)")
    df_comp_sec = pd.DataFrame(reg_data["comparativa_sectorial_regional"]).set_index("sector")
    st.bar_chart(df_comp_sec)
    st.dataframe(df_comp_sec.reset_index(), use_container_width=True, hide_index=True)