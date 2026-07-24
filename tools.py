import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from pathlib import Path
import numpy as np

# Variables globales para compartir memoria en el agente
_SESSION_DATA = {}

def cargar_bases_y_shapefile() -> str:
    """
    Tool 1: Carga las bases de mamógrafos, la población de mujeres y el Shapefile distrital.
    """
    # 1. Cargar bases
    df_mamo = pd.read_excel('Mamografos_RENIPRESS_Merge_FIX.xlsx')
    df_pob = pd.read_excel('afiliadas_40_69_por_domicilio.xlsx')
    
    # 2. Homologar el UBIGEO a 6 dígitos en formato texto para hacer el merge perfecto
    df_pob['UBIGEO_STR'] = df_pob['UBIGEO'].astype(str).str.zfill(6)
    df_mamo['UBIGEO_STR'] = df_mamo['RENIPRESS_UBIGEO'].astype(str).str.zfill(6)
    
    # 3. Limpiar coordenadas y crear la capa geoespacial (GeoDataFrame)
    df_mamo['RENIPRESS_NORTE'] = pd.to_numeric(df_mamo['RENIPRESS_NORTE'], errors='coerce')
    df_mamo['RENIPRESS_ESTE'] = pd.to_numeric(df_mamo['RENIPRESS_ESTE'], errors='coerce')
    df_mamo = df_mamo.dropna(subset=['RENIPRESS_NORTE', 'RENIPRESS_ESTE'])
    
    geom = [Point(xy) for xy in zip(df_mamo['RENIPRESS_ESTE'], df_mamo['RENIPRESS_NORTE'])]
    gdf_mamo = gpd.GeoDataFrame(df_mamo, geometry=geom, crs="EPSG:4326")
    
    # 4. Descargar el Shapefile distrital de Perú desde el repositorio abierto
    url_geojson = "https://github.com/juaneladio/peru-geojson/raw/master/peru_distrital_simple.geojson"
    peru_distritos = gpd.read_file(url_geojson)
    
    # 5. Guardar en memoria del agente
    _SESSION_DATA["gdf_mamo"] = gdf_mamo
    _SESSION_DATA["df_pob"] = df_pob
    _SESSION_DATA["peru_distritos"] = peru_distritos
    
    return f"Se cargaron {len(gdf_mamo)} mamógrafos y la base de demanda con éxito. Capa distrital lista."

def semaforizar_distrito(nombre_distrito: str) -> str:
    """
    Tool 2: Evalúa un distrito, cruza su población vs capacidad del hospital y genera el semáforo.
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
    
    # Buscar mamógrafos en ese distrito
    mamo_filtro = gdf_mamo[gdf_mamo['UBIGEO_STR'] == ubigeo_distrito]
    
    if mamo_filtro.empty:
        _SESSION_DATA["ultimo_distrito_sin_mamo"] = ubigeo_distrito
        recomendacion = "Recomendación: Priorizar envío de Mamógrafo Móvil." if demanda_afiliadas > 5000 else "Recomendación: Derivar a hospital cercano."
        return f"🔴 SEMÁFORO ROJO: El distrito {distrito_buscado} tiene {demanda_afiliadas} afiliadas objetivo y 0 mamógrafos. {recomendacion} Ejecuta calcular_mamografo_cercano para ver alternativas."
    
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
        estado = f"🟢 SEMÁFORO VERDE: Capacidad Instalada ({capacidad_total}) cubre la demanda de {demanda_afiliadas} mujeres. (Equipos Estáticos suficientes)."
    else:
        estado = f"🟡 SEMÁFORO ÁMBAR: La demanda ({demanda_afiliadas}) excede la capacidad del centro ({capacidad_total}). Recomendación: Mamógrafo parcial de apoyo."
        
    return estado

def calcular_mamografo_cercano(nombre_distrito: str) -> str:
    """
    Tool 3: Calcula la distancia en kilómetros al mamógrafo más cercano para distritos sin oferta.
    """
    gdf_mamo = _SESSION_DATA["gdf_mamo"]
    peru_distritos = _SESSION_DATA["peru_distritos"]
    distrito_buscado = str(nombre_distrito).upper().strip()
    
    # Buscar el polígono del distrito origen
    origen_geom = peru_distritos[peru_distritos['NOMBDEP'].str.upper() == distrito_buscado]
    if origen_geom.empty:
        # Intentar por NOMBPROV o NOMBDIST si tu geojson tiene esos campos (asumiremos NOMBDIST)
        origen_geom = peru_distritos[peru_distritos['NOMBDIST'].str.upper() == distrito_buscado]
        if origen_geom.empty:
            return "No se pudo geolocalizar el distrito en el Shapefile para medir distancia."
            
    # Obtener el centroide del distrito para medir distancia
    centroide_origen = origen_geom.geometry.centroid.iloc[0]
    
    # Calcular distancia usando GeoPandas proyectando a un CRS métrico local (ej. EPSG:32718) o un CRS proyectado general
    gdf_mamo_proj = gdf_mamo.to_crs(epsg=3857) # Pseudo-Mercator para metros
    centro_proj = gpd.GeoSeries([centroide_origen], crs="EPSG:4326").to_crs(epsg=3857).iloc[0]
    
    # Distancias
    distancias = gdf_mamo_proj.geometry.distance(centro_proj)
    indice_cercano = distancias.idxmin()
    distancia_km = distancias.min() / 1000  # Convertir metros a km
    
    hospital_cercano = gdf_mamo.loc[indice_cercano, 'RENIPRESS_NOMBRE']
    return f"El mamógrafo más cercano está en el establecimiento '{hospital_cercano}', a {distancia_km:.2f} km de distancia en línea recta."