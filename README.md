# 🏥 GeoAgent: Priorización de Cobertura de Mamógrafos en Perú

Este proyecto es un prototipo funcional desarrollado para el curso **Geo Agents: IA Generativa para el Análisis Geoespacial** del Q-LAB. 

El agente utiliza inteligencia artificial generativa y análisis geoespacial para cruzar la oferta de salud (RENIPRESS) con la demanda demográfica (afiliadas de 40 a 69 años), generando una semaforización de atención, ruteo de distancias a los 5 mamógrafos disponibles más cercanos (con su nivel de atención y la delimitación de sus distritos), un mapa nacional de cobertura y una recomendación final de acción priorizada.

## 🚀 Requisitos y Configuración

1. **Clonar el repositorio:**
   git clone https://github.com/AriRod09/geo-agent-mamografos.git

2. **Configurar el Token de IA:**
   * Crea un archivo llamado `.env` en la raíz del proyecto.
   * Copia el contenido de `.env.example` y añade tu API Key real de Gemini.

3. **Librerías necesarias:**
   Asegúrate de tener instaladas las siguientes librerías:
   pip install pandas geopandas shapely folium langchain-openai python-dotenv thefuzz[speedup] streamlit streamlit-folium deepagents langgraph

   `thefuzz` es opcional: si no está instalado, el agente simplemente omite la
   sugerencia de nombres de distrito parecidos ante errores de tipeo.

## 🏗️ Uso
- **Notebook:** abre `prototipo_agente.ipynb` y ejecuta las celdas para interactuar con el agente.
- **App web:** ejecuta `streamlit run app.py`. La app tiene dos pestañas:
  - **💬 Asistente:** chat con el agente (semáforo de cobertura, top-5 de mamógrafos
    más cercanos, mapa del distrito consultado, recomendación final).
  - **🗺️ Mapa Nacional de Centros:** mapa interactivo con todos los centros con
    mamógrafo del país, coloreados por nivel de atención y filtrables por categoría
    RENIPRESS. Está siempre disponible, sin necesidad de pedírselo al agente.

### 💬 Pregunta de ejemplo para el agente
Para que el agente use la mayoría de sus tools en un solo turno (carga de bases →
semáforo → cálculo de cercanos → mapa → recomendación), prueba con un distrito en
ROJO (sin mamógrafo propio) como Comas:

> "Evalúa la cobertura de mamógrafos en el distrito de Comas. Dime el estado del
> semáforo, si no hay mamógrafo indícame los más cercanos con su distancia y nivel
> de atención, genera el mapa de cobertura, y dame tu recomendación final."

Si quieres ver el flujo cuando sí hay mamógrafo (se omite el cálculo de cercanos),
usa el mismo prompt con **Ate** (ÁMBAR) o **Chalhuanca** (VERDE).

## 🛠️ Herramientas del Agente (Tools)

| # | Tool | Propósito |
|---|------|-----------|
| 1 | `cargar_bases_y_shapefile` | Carga los 62 centros de salud con mamógrafo, la demanda poblacional (afiliadas 40-69 años) y la capa distrital de Perú, ya pre-procesados. |
| 2 | `semaforizar_distrito` | Cruza la demanda poblacional del distrito contra la capacidad instalada y devuelve el semáforo (🟢 VERDE / 🟡 ÁMBAR / 🔴 ROJO). |
| 3 | `calcular_mamografo_cercano` | Si el distrito está en ROJO, calcula los 5 mamógrafos disponibles más cercanos, con distancia en km y nivel de atención de cada uno. |
| 4 | `generar_mapa_cobertura` | Genera un mapa interactivo (HTML/folium) con la delimitación del distrito consultado y, si está en ROJO, la delimitación de los distritos de los 5 hospitales alternativos más cercanos. |
| 5 | `generar_recomendacion` | **Se ejecuta siempre**, sin importar el color del semáforo. Sintetiza el análisis en una recomendación de acción priorizada (urgencia BAJA/MEDIA/ALTA). |

Además, `generar_mapa_nacional` (no es una tool del agente) arma el mapa con todos
los centros del país que se muestra en la pestaña fija de Streamlit.

## 🧠 Memoria, Output Estructurado y Guardarraíles
- **Memoria:** el agente conserva el historial de conversación entre turnos
  (`InMemorySaver`) y guarda en memoria de sesión los últimos resultados calculados
  (`ultimo_resultado`, `ultimo_cercanos`, `ultima_recomendacion`) para reutilizarlos
  entre tools sin recalcular.
- **Output estructurado:** cada tool, además de su respuesta en texto para el chat,
  guarda un diccionario estructurado que la UI de Streamlit renderiza como tarjetas,
  tabla y callout de recomendación.
- **Guardarraíles:**
  - Todas las tools resuelven el distrito por su código **UBIGEO** contra la base de
    población (única fuente de verdad), evitando confusiones entre los ~150 nombres
    de distrito que se repiten en distintas provincias del Perú.
  - Si el nombre de distrito no coincide exacto (error de tipeo), se sugiere
    automáticamente el más parecido con fuzzy matching (`thefuzz`, umbral 80% de
    similitud) en vez de fallar o alucinar un resultado.
  - `generar_recomendacion` es autosuficiente: si no encuentra en memoria el
    semáforo o los cercanos para el distrito consultado, los calcula internamente
    antes de recomendar.
