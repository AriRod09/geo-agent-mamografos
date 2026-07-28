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

# 3. Importar las Tools (incluye la nueva Tool 4 de mapa interactivo)
from tools import (
    cargar_bases_y_shapefile,
    semaforizar_distrito,
    calcular_mamografo_cercano,
    generar_mapa_cobertura,
)


# 4. >>> SYSTEM PROMPT <<<
system_prompt = """Eres un Analista Experto en Salud Pública Geoespacial para el Gobierno Peruano.
Tu objetivo es evaluar la cobertura de los servicios de mamografía en los distritos del Perú.

Cuando se te pregunte sobre un distrito, carga y sigue la habilidad 'peru-mammography-analysis'.
Usa los datos demográficos (mujeres de 40 a 69 años) y la capacidad instalada (categorías RENIPRESS) para determinar el estado del semáforo (Semaforización) del distrito:
- VERDE: La capacidad instalada cubre completamente la demanda poblacional local.
- ÁMBAR: Existe un mamógrafo, pero la demanda poblacional excede la capacidad del hospital.
- ROJO: No hay mamógrafos en el distrito. DEBES calcular la distancia en kilómetros al mamógrafo disponible más cercano.

Si el usuario solicita una visualización o un mapa, genera el mapa interactivo de cobertura usando la herramienta correspondiente.
Reporta las estadísticas exactas y proporciona las rutas de los mapas generados cuando se soliciten."""

# 5. Crear el GeoAgente conectando todo
agent = create_deep_agent(
    model=local_llm,
    tools=[
        cargar_bases_y_shapefile,
        semaforizar_distrito,
        calcular_mamografo_cercano,
        generar_mapa_cobertura,
    ],
    system_prompt=system_prompt,
    skills=["."] , # Esto le dice al agente que busque el archivo SKILL.md en la misma carpeta
    checkpointer=InMemorySaver()
)
