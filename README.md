# 🏥 GeoAgent: Priorización de Cobertura de Mamógrafos en Perú

Este proyecto es un prototipo funcional desarrollado para el curso **Geo Agents: IA Generativa para el Análisis Geoespacial** del Q-LAB. 

El agente utiliza inteligencia artificial generativa y análisis geoespacial para cruzar la oferta de salud (RENIPRESS) con la demanda demográfica (afiliadas de 40 a 69 años), generando una semaforización de atención y ruteo de distancias.

## 🚀 Requisitos y Configuración

1. **Clonar el repositorio:**
   git clone https://github.com/AriRod09/geo-agent-mamografos.git

2. **Configurar el Token de IA:**
   * Crea un archivo llamado `.env` en la raíz del proyecto.
   * Copia el contenido de `.env.example` y añade tu API Key real de Gemini.

3. **Librerías necesarias:**
   Asegúrate de tener instaladas las siguientes librerías:
   pip install pandas geopandas shapely folium langchain-openai python-dotenv thefuzz[speedup]

## 🏗️ Uso
Abre el archivo `prototipo_agente.ipynb` y ejecuta las celdas para interactuar con el agente.
