from langchain_openai import ChatOpenAI

# 1. Initialize the local LM Studio model
local_llm = ChatOpenAI(
    base_url="http://127.0.0.1:1234/v1",  # Points to LM Studio
    api_key="lm-studio",                 # LM Studio doesn't require a real key, but a placeholder string prevents errors
    model="gemma-4-e2b-it-qat",      # Match the name/identifier loaded in LM Studio
    temperature=0                       # Low temperature is critical for agent tool accuracy
)

# 1. Importar librerías necesarias
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver  # <-- ¡Esta es la línea que falta!
from dotenv import load_dotenv
import os

# 2. Cargar variables de entorno desde el archivo .env (si se usa algún proveedor externo)
load_dotenv()

# 3. Importar las Tools (incluye la Tool 4 de mapa interactivo y la Tool 5 de recomendación)
from tools import (
    cargar_bases_y_shapefile,
    semaforizar_distrito,
    calcular_mamografo_cercano,
    generar_mapa_cobertura,
    generar_recomendacion,
)


# 4. >>> SYSTEM PROMPT <<<
system_prompt = """Eres un Analista Experto en Salud Pública Geoespacial para el Gobierno Peruano.
Tu objetivo es evaluar la cobertura de los servicios de mamografía en los distritos del Perú.

Cuando se te pregunte sobre un distrito, carga y sigue la habilidad 'peru-mammography-analysis'.
Usa los datos demográficos (mujeres de 40 a 69 años) y la capacidad instalada (categorías RENIPRESS) para determinar el estado del semáforo (Semaforización) del distrito:
- VERDE: La capacidad instalada cubre completamente la demanda poblacional local.
- ÁMBAR: Existe un mamógrafo, pero la demanda poblacional excede la capacidad del hospital.
- ROJO: No hay mamógrafos en el distrito. DEBES calcular los 5 mamógrafos disponibles más cercanos (distancia en km y nivel de atención de cada uno) para ofrecer alternativas priorizadas.

Si el usuario escribe mal el nombre de un distrito, el sistema intentará sugerir automáticamente el nombre más parecido; comunica esa sugerencia al usuario de forma transparente.
Si el usuario solicita una visualización o un mapa, genera el mapa interactivo de cobertura usando la herramienta correspondiente. Cuando el distrito esté en ROJO, el mapa debe mostrar la delimitación del distrito y señalar los 5 centros más cercanos.

OBLIGATORIO: al finalizar el análisis de CUALQUIER distrito (sin importar si el semáforo salió VERDE, ÁMBAR o ROJO), SIEMPRE debes ejecutar la herramienta generar_recomendacion para entregar una recomendación de acción priorizada. Nunca termines tu respuesta sin haber llamado a esta herramienta.
Reporta las estadísticas exactas y proporciona las rutas de los mapas generados cuando se soliciten."""

# 5. Crear el GeoAgente conectando todo
agent = create_deep_agent(
    model=local_llm,
    tools=[
        cargar_bases_y_shapefile,
        semaforizar_distrito,
        calcular_mamografo_cercano,
        generar_mapa_cobertura,
        generar_recomendacion,
    ],
    system_prompt=system_prompt,
    skills=["."] , # Esto le dice al agente que busque el archivo SKILL.md en la misma carpeta
    checkpointer=InMemorySaver()
)
