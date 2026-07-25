# 🏥 GeoAgent: Priorización de Cobertura de Mamógrafos en Perú

Este proyecto es un prototipo funcional desarrollado para el curso **Geo Agents: IA Generativa para el Análisis Geoespacial** del Q-LAB. 

El agente utiliza inteligencia artificial generativa y análisis geoespacial para cruzar la oferta de salud (RENIPRESS) con la demanda demográfica (afiliadas de 40 a 69 años), generando una semaforización de atención y ruteo de distancias.

## Situación Actual

En el Perú, la planificación de intervenciones para la detección temprana del cáncer de mama enfrenta una limitación importante: la información sobre la ubicación de la población objetivo y la oferta de servicios de mamografía se encuentra dispersa en diferentes fuentes de datos y, por lo general, se analiza de manera independiente. Si bien registros como RENIPRESS permiten identificar los establecimientos de salud que disponen de mamógrafos, y las fuentes demográficas permiten estimar la distribución territorial de las mujeres de 40 a 69 años, actualmente no existe una herramienta que integre ambas dimensiones incorporando criterios de accesibilidad geográfica y distancia efectiva de desplazamiento.

Como consecuencia, resulta difícil identificar de manera objetiva qué distritos presentan mayores brechas de cobertura, cuáles concentran población potencialmente desatendida y qué establecimientos podrían atender dicha demanda mediante una redistribución o fortalecimiento de la oferta existente. Esta situación limita la priorización basada en evidencia y dificulta la asignación eficiente de recursos para programas de tamizaje y prevención del cáncer de mama.

## Oportunidad e impacto esperado

Se aborda esta problemática mediante un agente de inteligencia artificial generativa con capacidades de análisis geoespacial que integra información demográfica, infraestructura sanitaria y redes de transporte para estimar la cobertura territorial de los servicios de mamografía.

El agente identifica automáticamente los establecimientos de salud que disponen de mamógrafos, calcula la accesibilidad considerando la red vial, estima la población objetivo potencialmente atendida y detecta territorios donde la demanda supera la oferta disponible. A partir de este análisis genera mapas interactivos, indicadores de cobertura y recomendaciones que facilitan la priorización territorial de intervenciones.

El impacto esperado es mejorar la toma de decisiones de los gestores públicos mediante evidencia espacial, permitiendo orientar con mayor precisión la inversión pública, la adquisición o redistribución de mamógrafos, la implementación de campañas de tamizaje y la focalización de programas preventivos en las zonas con mayores brechas de acceso. De esta manera, el proyecto contribuye a una planificación sanitaria más eficiente, transparente y orientada a reducir las desigualdades territoriales en el acceso al diagnóstico oportuno del cáncer de mama.

## 📋 Componentes Principales del Agente

### 1. System Prompt: Instrucciones y Razonamiento General

El **System Prompt** establece el rol, dominio técnico y directrices operativas que rigen el comportamiento del agente:

* **Identidad y Rol:** Actúa como un *Analista de Salud Pública Geoespacial del Gobierno Peruano*.
* **Objetivo:** Cruzar datos demográficos con capacidad hospitalaria instalada para diagnosticar la accesibilidad a tamizajes de cáncer de mama.
* **Reglas de Negocio:**
  * Define a la población objetivo como **mujeres de 40 a 69 años**.
  * Clasifica el nivel de atención según el estado de la infraestructura disponible mediante un sistema de **Semaforización** (🟢 Verde, 🟡 Ámbar, 🔴 Rojo).
  * Gatilla de forma obligatoria el cálculo de distancias cuando se identifica un distrito sin oferta (🔴 Rojo).

---

### 2. Tools: Herramientas Geoespaciales y de Datos

El agente cuenta con 3 herramientas especializadas escritas en Python que extienden sus capacidades de análisis espacial:

| Herramienta | Función | Justificación Técnica |
| :--- | :--- | :--- |
| **`cargar_bases_y_shapefile`** | Carga y normaliza los datasets (demanda de afiliadas y oferta RENIPRESS), estandariza claves `UBIGEO` a 6 dígitos y descarga los límites distritales en GeoJSON. | Prepara la memoria de trabajo compartida (`_SESSION_DATA`) e independiza al LLM del procesamiento bruto de geometrías espaciales. |
| **`semaforizar_distrito`** | Evalúa un distrito específico, suma la población objetivo y calcula la capacidad instalada estimada (Nivel III: 15,000 atenciones/año; Nivel II: 7,500 atenciones/año). | Aplica el algoritmo cuantitativo de brecha entre Oferta y Demanda para determinar el color del semáforo distrital. |
| **`calcular_mamografo_cercano`** | Proyecta las geometrías a un sistema métrico (`EPSG:3857`), calcula el centroide del distrito sin oferta y mide la distancia Euclidiana (km) al mamógrafo más próximo. | Resuelve la brecha de acceso ofreciendo una alternativa geográfica concreta de derivación para zonas desatendidas. |

---

### 3. Skills: Flujo Lógico y Conexión Autónoma de Tools

El archivo `SKILL.md` define la "receta de razonamiento humano" que sigue el agente para resolver consultas complejas de manera secuencial:

```text
               [ 1. Carga de Entorno ]
              cargar_bases_y_shapefile()
                          │
                          ▼
            [ 2. Diagnóstico Distrital ]
             semaforizar_distrito(distrito)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
  🟢 VERDE / 🟡 ÁMBAR                  🔴 ROJO
(Capacidad evaluada)            (Sin mamógrafos)
          │                               │
          │                               ▼
          │                   [ 3. Solución Espacial ]
          │                 calcular_mamografo_cercano()
          │                               │
          └───────────────┬───────────────┘
                          ▼
             [ 4. Síntesis y Reporte ]
          Generación de informe institucional

## 🚀 Requisitos y Configuración

1. **Clonar el repositorio:**
   git clone https://github.com/AriRod09/geo-agent-mamografos.git

2. **Librerías necesarias:**
   Asegúrate de tener instaladas las siguientes librerías:
   pip install pandas geopandas shapely folium langchain-openai python-dotenv thefuzz[speedup]

## 🏗️ Uso
Abre el archivo `prototipo_agente.ipynb` y ejecuta las celdas para interactuar con el agente.
