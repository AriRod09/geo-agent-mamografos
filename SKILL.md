---
name: peru-mammography-analysis
description: Analiza y evalúa la cobertura y el acceso a servicios de mamografía en Perú.
---
# Análisis de Mamografía en Perú

## Resumen
Esta habilidad guía al agente para evaluar la cobertura de tamizaje de cáncer de mama,
cruzando la demanda demográfica con la capacidad instalada de los hospitales, generando
una alerta tipo semáforo (Semaforización) y, opcionalmente, un mapa interactivo de
cobertura.

## Referencia de Herramientas (Tools)

### 1. cargar_bases_y_shapefile
**Propósito:** Inicializar el entorno cargando la base pre-procesada de los 65 centros
de salud con mamógrafo, la base de demanda poblacional y la capa distrital de Perú.
Esta carga es rápida porque no realiza descargas ni limpiezas pesadas en tiempo real.
**Parámetros:** Ninguno.

### 2. semaforizar_distrito
**Propósito:** Evaluar a la población objetivo (mujeres de 40 a 69 años) frente a la
categoría hospitalaria de un distrito determinado. Debe ejecutarse DESPUÉS de cargar
las bases.
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito peruano a analizar.

### 3. calcular_mamografo_cercano
**Propósito:** Calcular los 5 centros con mamógrafo más cercanos (distancia exacta en
kilómetros y nivel de atención de cada uno), usando cálculo espacial. Ejecutar SOLO si
el distrito arroja resultado ROJO (0 mamógrafos).
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito.

### 4. generar_mapa_cobertura
**Propósito:** Generar un mapa interactivo en formato HTML (usando folium) que ubica
el polígono (delimitación) del distrito evaluado. Si el distrito tiene mamógrafos
propios, coloca marcadores sobre ellos. Si NO tiene (ROJO), señala en el mapa los 5
centros con mamógrafo más cercanos, cada uno con su distancia y nivel de atención.
Guarda el archivo HTML resultante en disco.
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito a mapear.

### 5. generar_recomendacion
**Propósito:** Generar la recomendación final de acción (nivel de urgencia + medida
concreta) en base al semáforo, la demanda, la capacidad instalada y, si el distrito
está en ROJO, la distancia al mamógrafo más cercano. Es autosuficiente: si falta
información en memoria de sesión, la calcula internamente. **Se debe ejecutar SIEMPRE,
sin importar el color del semáforo.**
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito.

## Guardarraíles
- **Resolución de distrito por UBIGEO:** todas las tools resuelven el distrito contra
  la base de población (única fuente de verdad) usando su código UBIGEO, evitando
  confusiones entre distritos homónimos (en Perú hay ~150 nombres de distrito
  repetidos en distintas provincias).
- **Corrección de errores de tipeo:** si el nombre no coincide exactamente, se usa
  fuzzy matching (`thefuzz`) para sugerir el distrito más parecido (umbral 80% de
  similitud) en lugar de fallar silenciosamente o alucinar un resultado.

## Flujo de Ejecución (Workflow)
1. Siempre comienza ejecutando `cargar_bases_y_shapefile()` para cargar el estado inicial.
2. Cuando el usuario pregunte por un distrito, ejecuta `semaforizar_distrito(nombre_distrito)`.
3. Si el resultado es "🔴 SEMÁFORO ROJO", ejecuta inmediatamente
   `calcular_mamografo_cercano(nombre_distrito)` para ofrecer al usuario las 5
   alternativas disponibles más cercanas, ordenadas por distancia.
4. Si el usuario solicita una visualización, un mapa, o quiere "ver" la cobertura del
   distrito, ejecuta `generar_mapa_cobertura(nombre_distrito)` y comparte la ruta del
   archivo HTML generado.
5. **SIEMPRE**, sin importar el color del semáforo, ejecuta al final
   `generar_recomendacion(nombre_distrito)` para obtener la recomendación de acción
   priorizada (urgencia BAJA/MEDIA/ALTA).
6. Sintetiza los hallazgos de forma clara y en español, indicando el estado del
   semáforo, la demanda, la capacidad instalada, si corresponde el ranking de
   establecimientos alternativos (distancia y nivel de atención) y la ruta del mapa
   generado, y cierra siempre con la recomendación de acción.

Nota: el mapa con TODOS los centros de salud del país (vista nacional) no es una tool
del agente; se muestra siempre en una pestaña fija de la interfaz de Streamlit
(`app.py`), independiente del chat.