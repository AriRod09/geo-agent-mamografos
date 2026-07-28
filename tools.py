import pandas as pd
import geopandas as gpd
import folium
from pathlib import Path

# Variables globales para compartir memoria en el agente
_SESSION_DATA = {}

def get_session_data():
    return _SESSION_DATA

# Agrega esto:
def clear_session_data():
    _SESSION_DATA.clear()


def _nivel_legible(categoria: str) -> str:
    """Traduce la categoría RENIPRESS (ej. 'II-1') a un nivel de atención legible."""
    cat = str(categoria)
    if cat.startswith("III"):
        return "Nivel III (Hospital especializado)"
    if cat.startswith("II"):
        return "Nivel II (Hospital)"
    return "Nivel I (Centro/Puesto de salud)"


def _resolver_ubigeo_distrito(nombre_distrito: str):
    """
    Guardarraíl de resolución de distrito: busca el UBIGEO exacto en la base de
    población (fuente única de verdad para nombres de distrito) y, si no
    encuentra coincidencia exacta, sugiere el nombre más parecido con fuzzy
    matching (thefuzz) para evitar respuestas erróneas por typos.

    Devuelve (ubigeo, nombre_resuelto, nota) o (None, nombre_buscado, None) si
    no se pudo resolver ninguna coincidencia razonable.
    """
    df_pob = _SESSION_DATA["df_pob"]
    distrito_buscado = str(nombre_distrito).upper().strip()

    filtro = df_pob[df_pob["DISTRITO"].str.upper() == distrito_buscado]
    if not filtro.empty:
        return filtro["UBIGEO_STR"].iloc[0], distrito_buscado, None

    # Fallback: fuzzy matching para tolerar errores de tipeo o acentos
    try:
        from thefuzz import process

        opciones = df_pob["DISTRITO"].dropna().unique().tolist()
        match, score = process.extractOne(distrito_buscado, opciones)
        if score >= 80:
            filtro_fuzzy = df_pob[df_pob["DISTRITO"] == match]
            nota = f"⚠️ No se encontró '{distrito_buscado}' exacto. Se interpretó como '{match}' ({score}% similitud)."
            return filtro_fuzzy["UBIGEO_STR"].iloc[0], match, nota
    except ImportError:
        pass

    return None, distrito_buscado, None


def _centroide_distrito(ubigeo_distrito: str):
    """Devuelve (fila_geom_distrito, centroide_lonlat) para un UBIGEO dado."""
    peru_distritos = _SESSION_DATA["peru_distritos"]
    origen_geom = peru_distritos[
        peru_distritos["IDDIST"].astype(str).str.zfill(6) == ubigeo_distrito
    ]
    if origen_geom.empty:
        return None, None
    origen_proj = origen_geom.to_crs(epsg=3857)
    centroide_proj = origen_proj.geometry.centroid.iloc[0]
    return origen_geom, centroide_proj


def _calcular_cercanos(ubigeo_distrito: str, top_n: int = 5):
    """
    Calcula los `top_n` centros con mamógrafo más cercanos al centroide de un
    distrito, devolviendo un GeoDataFrame ordenado por distancia (columna
    'distancia_km') y la geometría del distrito de origen.
    """
    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    origen_geom, centroide_proj = _centroide_distrito(ubigeo_distrito)
    if origen_geom is None:
        return None, None

    gdf_mamo_proj = gdf_mamo.to_crs(epsg=3857)
    distancias_km = gdf_mamo_proj.geometry.distance(centroide_proj) / 1000

    resultado = gdf_mamo.copy()
    resultado["distancia_km"] = distancias_km.values
    resultado = resultado.sort_values("distancia_km").head(top_n).reset_index(drop=True)
    return origen_geom, resultado


def cargar_bases_y_shapefile() -> str:
    """
    Tool 1: Carga la base pre-procesada de los 65 centros de salud con mamógrafo,
    la base de demanda poblacional y la capa distrital de Perú.

    OPTIMIZACIÓN: A diferencia de la versión anterior, esta función ya NO descarga
    el Shapefile desde internet ni realiza limpiezas o merges pesados en tiempo real.
    Todo el preprocesamiento (homologación de UBIGEO, limpieza de coordenadas,
    filtrado a los 65 establecimientos con mamógrafo) se hizo una sola vez de forma
    offline y se guardó en archivos listos para usar dentro de la carpeta 'data'.
    """
    base_dir = Path(__file__).parent / "data"

    # 1. Cargar la base ya procesada de centros de salud con mamógrafo (65 registros)
    gdf_mamo = gpd.read_file(base_dir / "mamografos_procesado.geojson")

    # 2. Cargar la base de demanda poblacional (mujeres afiliadas 40-69 años)
    df_pob = pd.read_parquet(base_dir / "afiliadas_40_69_procesado.parquet")

    # 3. Cargar la capa distrital de Perú (guardada localmente, sin descarga remota)
    peru_distritos = gpd.read_file(base_dir / "peru_distrital_simple.geojson")

    # 4. Guardar todo en la memoria de sesión del agente
    _SESSION_DATA["gdf_mamo"] = gdf_mamo
    _SESSION_DATA["df_pob"] = df_pob
    _SESSION_DATA["peru_distritos"] = peru_distritos

    return (
        f"Se cargaron {len(gdf_mamo)} centros de salud con mamógrafo y la base de "
        f"demanda poblacional con éxito. Capa distrital lista. (Carga optimizada: "
        f"sin descargas ni procesamiento pesado en tiempo real)."
    )


def semaforizar_distrito(nombre_distrito: str) -> str:
    """
    Tool 2: Evalúa un distrito, cruza la población objetivo contra la capacidad
    instalada de los centros con mamógrafo y genera el semáforo de cobertura.
    Requiere que cargar_bases_y_shapefile() se haya ejecutado primero.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    df_pob = _SESSION_DATA["df_pob"]
    gdf_mamo = _SESSION_DATA["gdf_mamo"]

    # Guardarraíl: resolver el distrito por UBIGEO (única fuente de verdad),
    # con sugerencia fuzzy si el nombre no coincide exactamente.
    ubigeo_distrito, distrito_resuelto, nota = _resolver_ubigeo_distrito(nombre_distrito)
    if ubigeo_distrito is None:
        return f"No se encontró información de población para el distrito '{nombre_distrito}'."

    pob_filtro = df_pob[df_pob["UBIGEO_STR"] == ubigeo_distrito]
    demanda_afiliadas = pob_filtro["TOTAL_AFILIADOS"].sum()

    # Buscar centros con mamógrafo en ese distrito (mismo UBIGEO exacto)
    mamo_filtro = gdf_mamo[gdf_mamo["UBIGEO_STR"] == ubigeo_distrito]

    prefijo = f"{nota}\n\n" if nota else ""

    # Memoria de sesión: se reutiliza en calcular_mamografo_cercano / generar_mapa_cobertura
    _SESSION_DATA["ultimo_ubigeo"] = ubigeo_distrito
    _SESSION_DATA["ultimo_distrito_nombre"] = distrito_resuelto

    if mamo_filtro.empty:
        recomendacion = (
            "Recomendación: Priorizar envío de Mamógrafo Móvil."
            if demanda_afiliadas > 5000
            else "Recomendación: Derivar a hospital cercano."
        )
        estado = "🔴 SEMÁFORO ROJO"
        resultado_texto = (
            f"{estado}: El distrito {distrito_resuelto} tiene {demanda_afiliadas} "
            f"afiliadas objetivo y 0 mamógrafos. {recomendacion} "
            f"Ejecuta calcular_mamografo_cercano para ver alternativas."
        )
        capacidad_total = 0
    else:
        # Calcular capacidad instalada estimada (Nivel III = 15k mujeres/año, Nivel II = 7.5k mujeres/año)
        capacidad_total = 0
        for idx, row in mamo_filtro.iterrows():
            cat = str(row["CATEGORIA"])
            equipos = row["N_MAMOGRAFOS"] if pd.notnull(row["N_MAMOGRAFOS"]) else 1
            if "III" in cat:
                capacidad_total += 15000 * equipos
            else:
                capacidad_total += 7500 * equipos

        if capacidad_total >= demanda_afiliadas:
            estado = "🟢 SEMÁFORO VERDE"
            resultado_texto = (
                f"{estado}: Capacidad Instalada ({capacidad_total}) cubre la demanda "
                f"de {demanda_afiliadas} mujeres. (Equipos Estáticos suficientes)."
            )
        else:
            estado = "🟡 SEMÁFORO ÁMBAR"
            resultado_texto = (
                f"{estado}: La demanda ({demanda_afiliadas}) excede la capacidad del "
                f"centro ({capacidad_total}). Recomendación: Mamógrafo parcial de apoyo."
            )

    # Output estructurado: se guarda en memoria de sesión para que la UI (Streamlit)
    # pueda renderizarlo como tarjetas/métricas además del texto conversacional.
    _SESSION_DATA["ultimo_resultado"] = {
        "distrito": distrito_resuelto,
        "ubigeo": ubigeo_distrito,
        "demanda_afiliadas": int(demanda_afiliadas),
        "capacidad_instalada": int(capacidad_total),
        "n_centros": int(len(mamo_filtro)),
        "semaforo": estado,
    }

    return prefijo + resultado_texto


def calcular_mamografo_cercano(nombre_distrito: str) -> str:
    """
    Tool 3: Calcula los 5 centros con mamógrafo más cercanos a un distrito sin
    oferta propia, indicando distancia en kilómetros y nivel de atención de
    cada uno, para que el usuario tenga alternativas priorizadas por cercanía.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    ubigeo_distrito, distrito_resuelto, nota = _resolver_ubigeo_distrito(nombre_distrito)
    if ubigeo_distrito is None:
        return f"No se pudo resolver el distrito '{nombre_distrito}' para calcular distancias."

    origen_geom, cercanos = _calcular_cercanos(ubigeo_distrito, top_n=5)
    if origen_geom is None:
        return "No se pudo geolocalizar el distrito en el Shapefile para medir la distancia."

    _SESSION_DATA["ultimo_ubigeo"] = ubigeo_distrito
    _SESSION_DATA["ultimo_distrito_nombre"] = distrito_resuelto

    # Output estructurado (lista de dicts) para reutilizar en el mapa y en la UI
    lista_estructurada = [
        {
            "ranking": i + 1,
            "establecimiento": row["RENIPRESS_NOMBRE"],
            "nivel_atencion": _nivel_legible(row["CATEGORIA"]),
            "categoria": row["CATEGORIA"],
            "distancia_km": round(row["distancia_km"], 2),
        }
        for i, row in cercanos.iterrows()
    ]
    _SESSION_DATA["ultimo_cercanos"] = lista_estructurada

    prefijo = f"{nota}\n\n" if nota else ""
    lineas = [
        f"Los 5 mamógrafos más cercanos a {distrito_resuelto} son:",
    ]
    for c in lista_estructurada:
        lineas.append(
            f"{c['ranking']}. {c['establecimiento']} — {c['nivel_atencion']} — "
            f"{c['distancia_km']} km"
        )
    return prefijo + "\n".join(lineas)


def generar_mapa_cobertura(nombre_distrito: str) -> str:
    """
    Tool 4: Genera un mapa interactivo (HTML) con folium para el distrito evaluado.
    Dibuja la delimitación (polígono) del distrito consultado. Si el distrito tiene
    mamógrafos propios, coloca marcadores sobre ellos. Si NO tiene (semáforo rojo),
    coloca marcadores numerados de los 5 centros con mamógrafo más cercanos,
    indicando distancia y nivel de atención de cada uno.
    Requiere que cargar_bases_y_shapefile() se haya ejecutado primero.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    peru_distritos = _SESSION_DATA["peru_distritos"]

    ubigeo_distrito, distrito_resuelto, nota = _resolver_ubigeo_distrito(nombre_distrito)
    if ubigeo_distrito is None:
        return f"No se pudo resolver el distrito '{nombre_distrito}' para generar el mapa."

    origen_geom, centroide_proj = _centroide_distrito(ubigeo_distrito)
    if origen_geom is None:
        return "No se pudo geolocalizar el distrito para generar el mapa."

    centroide_4326 = gpd.GeoSeries([centroide_proj], crs=3857).to_crs(epsg=4326).iloc[0]
    mapa = folium.Map(location=[centroide_4326.y, centroide_4326.x], zoom_start=12, tiles="OpenStreetMap")

    # 1. Dibujar el polígono (delimitación) del distrito evaluado
    folium.GeoJson(
        origen_geom,
        name=f"Distrito: {distrito_resuelto}",
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#3388ff",
            "weight": 2,
            "fillOpacity": 0.15,
        },
    ).add_to(mapa)

    # 2. Centros con mamógrafo dentro del mismo distrito (mismo UBIGEO exacto)
    mamo_filtro = gdf_mamo[gdf_mamo["UBIGEO_STR"] == ubigeo_distrito]

    if not mamo_filtro.empty:
        for idx, row in mamo_filtro.iterrows():
            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                popup=(
                    f"{row.get('RENIPRESS_NOMBRE', 'Establecimiento')} "
                    f"({_nivel_legible(row.get('CATEGORIA', ''))})"
                ),
                tooltip=row.get("RENIPRESS_NOMBRE", "Establecimiento con mamógrafo"),
                icon=folium.Icon(color="green", icon="plus-sign"),
            ).add_to(mapa)
    else:
        # 3. Distrito sin mamógrafo propio: señalar los 5 más cercanos en el mapa,
        # delimitando también el distrito de cada hospital alternativo.
        _, cercanos = _calcular_cercanos(ubigeo_distrito, top_n=5)
        colores_ranking = ["red", "orange", "orange", "beige", "beige"]
        hex_ranking = ["#e6194b", "#f58231", "#f58231", "#c9a66b", "#c9a66b"]

        bounds = list(origen_geom.total_bounds)  # [minx, miny, maxx, maxy]
        distritos_dibujados = set()

        for i, row in cercanos.iterrows():
            ubigeo_hospital = row["UBIGEO_STR"]

            # Delimitar el distrito donde se ubica este hospital (si aún no se dibujó)
            if ubigeo_hospital not in distritos_dibujados:
                distrito_hospital_geom = peru_distritos[
                    peru_distritos["IDDIST"].astype(str).str.zfill(6) == ubigeo_hospital
                ]
                if not distrito_hospital_geom.empty:
                    nombre_distrito_hospital = distrito_hospital_geom["NOMBDIST"].iloc[0]
                    folium.GeoJson(
                        distrito_hospital_geom,
                        name=f"Distrito hospital #{i + 1}: {nombre_distrito_hospital}",
                        style_function=lambda feature, color=hex_ranking[i]: {
                            "fillColor": color,
                            "color": color,
                            "weight": 2,
                            "fillOpacity": 0.1,
                            "dashArray": "4,4",
                        },
                        tooltip=f"Distrito: {nombre_distrito_hospital} (hospital #{i + 1})",
                    ).add_to(mapa)
                    bounds_hosp = distrito_hospital_geom.total_bounds
                    bounds[0] = min(bounds[0], bounds_hosp[0])
                    bounds[1] = min(bounds[1], bounds_hosp[1])
                    bounds[2] = max(bounds[2], bounds_hosp[2])
                    bounds[3] = max(bounds[3], bounds_hosp[3])
                distritos_dibujados.add(ubigeo_hospital)

            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                popup=(
                    f"#{i + 1} {row['RENIPRESS_NOMBRE']} — "
                    f"{_nivel_legible(row['CATEGORIA'])} — {row['distancia_km']:.2f} km"
                ),
                tooltip=f"#{i + 1} · {row['distancia_km']:.2f} km",
                icon=folium.Icon(color=colores_ranking[i], icon="plus-sign"),
            ).add_to(mapa)
            folium.PolyLine(
                locations=[[centroide_4326.y, centroide_4326.x], [row.geometry.y, row.geometry.x]],
                color="gray",
                weight=1,
                dash_array="5,5",
            ).add_to(mapa)

        folium.Marker(
            location=[centroide_4326.y, centroide_4326.x],
            popup=f"Distrito {distrito_resuelto}: sin mamógrafos propios",
            icon=folium.Icon(color="darkred", icon="remove-sign"),
        ).add_to(mapa)

        # Ajustar el zoom para que se vean el distrito consultado y los distritos
        # de los 5 hospitales alternativos, sin importar qué tan lejos estén.
        mapa.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        leyenda_html = """
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                    background-color: white; padding: 10px 14px; border-radius: 6px;
                    border: 1px solid #999; font-size: 13px;">
            <b>Ranking por cercanía</b><br>
            <span style="color:red;">●</span> #1 (más cercano)<br>
            <span style="color:orange;">●</span> #2 - #3<br>
            <span style="color:#c9a66b;">●</span> #4 - #5<br>
            <span style="color:darkred;">●</span> Centroide del distrito consultado<br>
            <span style="color:#3388ff;">▭</span> Distrito consultado (delimitación)<br>
            <span style="color:#666;">▭ punteado</span> Distrito de cada hospital alternativo
        </div>
        """
        mapa.get_root().html.add_child(folium.Element(leyenda_html))

    # 4. Guardar el mapa como archivo HTML
    salida_dir = Path(__file__).parent / "mapas_salida"
    salida_dir.mkdir(exist_ok=True)
    nombre_archivo = f"mapa_cobertura_{distrito_resuelto.replace(' ', '_')}.html"
    ruta_salida = salida_dir / nombre_archivo
    mapa.save(str(ruta_salida))

    # Guardar el mapa en memoria para que Streamlit lo lea
    _SESSION_DATA["pending_map"] = mapa
    _SESSION_DATA["map_title"] = f"Mapa de Cobertura: {distrito_resuelto}"

    prefijo = f"{nota}\n\n" if nota else ""
    return prefijo + f"Mapa de cobertura generado con éxito en: {ruta_salida}"


def generar_recomendacion(nombre_distrito: str) -> str:
    """
    Tool 5: Genera la recomendación final de acción para un distrito, en base al
    semáforo, la demanda, la capacidad instalada y (si aplica) la distancia al
    mamógrafo más cercano. Esta tool debe ejecutarse SIEMPRE al final del
    análisis de cualquier distrito, sin importar el color del semáforo.

    Es autosuficiente: si no encuentra en memoria de sesión el resultado del
    semáforo (o de los cercanos, cuando corresponde) para este distrito, los
    calcula internamente antes de generar la recomendación.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    ubigeo_distrito, distrito_resuelto, nota = _resolver_ubigeo_distrito(nombre_distrito)
    if ubigeo_distrito is None:
        return f"No se pudo resolver el distrito '{nombre_distrito}' para generar una recomendación."

    # Asegurar que el semáforo en memoria corresponda a este distrito
    resultado = _SESSION_DATA.get("ultimo_resultado")
    if not resultado or resultado.get("ubigeo") != ubigeo_distrito:
        semaforizar_distrito(nombre_distrito)
        resultado = _SESSION_DATA.get("ultimo_resultado")

    semaforo = resultado["semaforo"]
    demanda = resultado["demanda_afiliadas"]
    capacidad = resultado["capacidad_instalada"]

    distancia_mas_cercano = None
    if "ROJO" in semaforo:
        cercanos = _SESSION_DATA.get("ultimo_cercanos")
        if not cercanos or _SESSION_DATA.get("ultimo_ubigeo") != ubigeo_distrito:
            calcular_mamografo_cercano(nombre_distrito)
            cercanos = _SESSION_DATA.get("ultimo_cercanos")
        if cercanos:
            distancia_mas_cercano = cercanos[0]["distancia_km"]

    # --- Lógica de priorización ---
    if "VERDE" in semaforo:
        urgencia = "BAJA"
        accion = (
            "Mantener monitoreo periódico de la demanda. La capacidad instalada "
            "cubre a la población objetivo; no se requiere intervención inmediata."
        )
    elif "ÁMBAR" in semaforo:
        urgencia = "MEDIA"
        accion = (
            "Gestionar turnos adicionales o un mamógrafo de apoyo temporal. La "
            "demanda supera la capacidad instalada del distrito y puede generar "
            "listas de espera."
        )
    else:  # ROJO
        if distancia_mas_cercano is not None and distancia_mas_cercano <= 15:
            urgencia = "MEDIA"
            accion = (
                f"Derivar activamente a las pacientes al establecimiento más cercano "
                f"({distancia_mas_cercano:.2f} km), ya que está a una distancia razonable, "
                f"mientras se evalúa ampliar la oferta local."
            )
        elif distancia_mas_cercano is not None and (distancia_mas_cercano > 50 or demanda > 5000):
            urgencia = "ALTA"
            accion = (
                f"Priorizar el envío de un mamógrafo móvil/itinerante: alta demanda "
                f"({demanda} afiliadas) y sin alternativa cercana "
                f"(mamógrafo más próximo a {distancia_mas_cercano:.2f} km)."
            )
        else:
            urgencia = "ALTA"
            distancia_txt = f"{distancia_mas_cercano:.2f} km" if distancia_mas_cercano is not None else "desconocida"
            accion = (
                f"Coordinar referencia programada de pacientes al establecimiento "
                f"alternativo (distancia: {distancia_txt}) y evaluar la factibilidad "
                f"de un mamógrafo móvil según presupuesto disponible."
            )

    _SESSION_DATA["ultima_recomendacion"] = {
        "distrito": distrito_resuelto,
        "urgencia": urgencia,
        "accion_recomendada": accion,
    }

    prefijo = f"{nota}\n\n" if nota else ""
    return (
        f"{prefijo}📋 Recomendación para {distrito_resuelto} (urgencia {urgencia}): {accion}"
    )


def generar_mapa_nacional(categorias_filtro=None):
    """
    Construye (sin guardarlo como Tool del agente) un mapa folium con TODOS los
    centros de salud con mamógrafo a nivel nacional, coloreados por nivel de
    atención. Pensado para mostrarse siempre en una sección fija de la UI de
    Streamlit (no requiere que el usuario se lo pida al agente por chat).

    `categorias_filtro`: lista opcional de valores de CATEGORIA (ej. ['III-1','III-2'])
    para filtrar qué centros se dibujan.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        raise RuntimeError("Ejecuta cargar_bases_y_shapefile primero.")

    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    if categorias_filtro:
        gdf_mamo = gdf_mamo[gdf_mamo["CATEGORIA"].isin(categorias_filtro)]

    mapa = folium.Map(location=[-9.19, -75.02], zoom_start=5, tiles="OpenStreetMap")

    color_por_nivel = {
        "Nivel III (Hospital especializado)": "green",
        "Nivel II (Hospital)": "blue",
        "Nivel I (Centro/Puesto de salud)": "orange",
    }

    for idx, row in gdf_mamo.iterrows():
        nivel = _nivel_legible(row["CATEGORIA"])
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=6,
            color=color_por_nivel.get(nivel, "gray"),
            fill=True,
            fill_opacity=0.85,
            popup=(
                f"{row['RENIPRESS_NOMBRE']}<br>{nivel} ({row['CATEGORIA']})<br>"
                f"{row.get('N_MAMOGRAFOS', 1)} equipo(s)"
            ),
            tooltip=row["RENIPRESS_NOMBRE"],
        ).add_to(mapa)

    leyenda_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background-color: white; padding: 10px 14px; border-radius: 6px;
                border: 1px solid #999; font-size: 13px;">
        <b>Nivel de atención</b><br>
        <span style="color:green;">●</span> Nivel III (Hospital especializado)<br>
        <span style="color:blue;">●</span> Nivel II (Hospital)<br>
        <span style="color:orange;">●</span> Nivel I (Centro/Puesto de salud)
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(leyenda_html))

    return mapa
