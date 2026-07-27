import pandas as pd
import geopandas as gpd
import folium
from pathlib import Path

# Variables globales para compartir memoria en el agente
_SESSION_DATA = {}


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

    # Filtrar población del distrito buscado
    distrito_buscado = str(nombre_distrito).upper().strip()
    pob_filtro = df_pob[df_pob['DISTRITO'].str.upper() == distrito_buscado]

    if pob_filtro.empty:
        return f"No se encontró información de población para el distrito {distrito_buscado}."

    demanda_afiliadas = pob_filtro['TOTAL_AFILIADOS'].sum()
    ubigeo_distrito = pob_filtro['UBIGEO_STR'].iloc[0]

    # Buscar centros con mamógrafo en ese distrito
    mamo_filtro = gdf_mamo[gdf_mamo['UBIGEO_STR'] == ubigeo_distrito]

    if mamo_filtro.empty:
        _SESSION_DATA["ultimo_distrito_sin_mamo"] = ubigeo_distrito
        recomendacion = (
            "Recomendación: Priorizar envío de Mamógrafo Móvil."
            if demanda_afiliadas > 5000
            else "Recomendación: Derivar a hospital cercano."
        )
        return (
            f"🔴 SEMÁFORO ROJO: El distrito {distrito_buscado} tiene {demanda_afiliadas} "
            f"afiliadas objetivo y 0 mamógrafos. {recomendacion} "
            f"Ejecuta calcular_mamografo_cercano para ver alternativas."
        )

    # Calcular capacidad instalada estimada (Nivel III = 15k mujeres/año, Nivel II = 7.5k mujeres/año)
    capacidad_total = 0
    for idx, row in mamo_filtro.iterrows():
        cat = str(row['CATEGORIA'])
        equipos = row['N_MAMOGRAFOS'] if pd.notnull(row['N_MAMOGRAFOS']) else 1
        if 'III' in cat:
            capacidad_total += (15000 * equipos)
        else:
            capacidad_total += (7500 * equipos)

    if capacidad_total >= demanda_afiliadas:
        estado = (
            f"🟢 SEMÁFORO VERDE: Capacidad Instalada ({capacidad_total}) cubre la demanda "
            f"de {demanda_afiliadas} mujeres. (Equipos Estáticos suficientes)."
        )
    else:
        estado = (
            f"🟡 SEMÁFORO ÁMBAR: La demanda ({demanda_afiliadas}) excede la capacidad del "
            f"centro ({capacidad_total}). Recomendación: Mamógrafo parcial de apoyo."
        )

    return estado


def calcular_mamografo_cercano(nombre_distrito: str) -> str:
    """
    Tool 3: Calcula la distancia en kilómetros al centro con mamógrafo más cercano
    para distritos sin oferta propia.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    peru_distritos = _SESSION_DATA["peru_distritos"]
    distrito_buscado = str(nombre_distrito).upper().strip()

    # Buscar el polígono del distrito origen
    origen_geom = peru_distritos[peru_distritos['NOMBDEP'].str.upper() == distrito_buscado]
    if origen_geom.empty:
        # Intentar por NOMBDIST si el geojson maneja ese campo
        origen_geom = peru_distritos[peru_distritos['NOMBDIST'].str.upper() == distrito_buscado]
        if origen_geom.empty:
            return "No se pudo geolocalizar el distrito en el Shapefile para medir la distancia."

    # Proyectar a un CRS métrico antes de calcular el centroide (evita advertencias y errores de precisión)
    origen_proj = origen_geom.to_crs(epsg=3857)
    centroide_proj = origen_proj.geometry.centroid.iloc[0]

    # Proyectar los centros con mamógrafo al mismo CRS métrico
    gdf_mamo_proj = gdf_mamo.to_crs(epsg=3857)

    # Calcular distancias
    distancias = gdf_mamo_proj.geometry.distance(centroide_proj)
    indice_cercano = distancias.idxmin()
    distancia_km = distancias.min() / 1000  # Convertir metros a km

    hospital_cercano = gdf_mamo.loc[indice_cercano, 'RENIPRESS_NOMBRE']
    return (
        f"El mamógrafo más cercano está en el establecimiento '{hospital_cercano}', "
        f"a {distancia_km:.2f} km de distancia en línea recta."
    )


def generar_mapa_cobertura(nombre_distrito: str) -> str:
    """
    Tool 4: Genera un mapa interactivo (HTML) con folium para el distrito evaluado.
    Ubica el polígono del distrito y coloca marcadores en los centros de salud
    con mamógrafo disponibles en la zona. Guarda el archivo HTML resultante.
    Requiere que cargar_bases_y_shapefile() se haya ejecutado primero.
    """
    if "gdf_mamo" not in _SESSION_DATA:
        return "Error: Ejecuta cargar_bases_y_shapefile primero."

    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    peru_distritos = _SESSION_DATA["peru_distritos"]
    distrito_buscado = str(nombre_distrito).upper().strip()

    # 1. Ubicar el polígono del distrito
    origen_geom = peru_distritos[peru_distritos['NOMBDEP'].str.upper() == distrito_buscado]
    if origen_geom.empty:
        origen_geom = peru_distritos[peru_distritos['NOMBDIST'].str.upper() == distrito_buscado]
        if origen_geom.empty:
            return "No se pudo geolocalizar el distrito para generar el mapa."

    # 2. Calcular el centro del mapa a partir del centroide del distrito (en CRS geográfico para folium)
    centroide = origen_geom.geometry.centroid.iloc[0]
    mapa = folium.Map(location=[centroide.y, centroide.x], zoom_start=12, tiles="OpenStreetMap")

    # 3. Dibujar el polígono del distrito evaluado
    folium.GeoJson(
        origen_geom,
        name=f"Distrito: {distrito_buscado}",
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#3388ff",
            "weight": 2,
            "fillOpacity": 0.15,
        },
    ).add_to(mapa)

    # 4. Colocar marcadores para los centros con mamógrafo dentro del distrito
    ubigeo_distrito = origen_geom['UBIGEO_STR'].iloc[0] if 'UBIGEO_STR' in origen_geom.columns else None
    if ubigeo_distrito is not None:
        mamo_filtro = gdf_mamo[gdf_mamo['UBIGEO_STR'] == ubigeo_distrito]
    else:
        mamo_filtro = gdf_mamo.iloc[0:0]  # vacío si no se puede filtrar por UBIGEO

    for idx, row in mamo_filtro.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=f"{row.get('RENIPRESS_NOMBRE', 'Establecimiento')} ({row.get('CATEGORIA', 'S/D')})",
            tooltip=row.get('RENIPRESS_NOMBRE', 'Establecimiento con mamógrafo'),
            icon=folium.Icon(color="green", icon="plus-sign"),
        ).add_to(mapa)

    if mamo_filtro.empty:
        # Sin mamógrafos en el distrito: marcar el centroide como referencia de zona sin cobertura
        folium.Marker(
            location=[centroide.y, centroide.x],
            popup="Distrito sin mamógrafos propios",
            icon=folium.Icon(color="red", icon="remove-sign"),
        ).add_to(mapa)

    # 5. Guardar el mapa como archivo HTML
    salida_dir = Path(__file__).parent / "mapas_salida"
    salida_dir.mkdir(exist_ok=True)
    nombre_archivo = f"mapa_cobertura_{distrito_buscado.replace(' ', '_')}.html"
    ruta_salida = salida_dir / nombre_archivo
    mapa.save(str(ruta_salida))

    return f"Mapa de cobertura generado con éxito en: {ruta_salida}"