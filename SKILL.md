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
**Propósito:** Calcular la distancia exacta en kilómetros al mamógrafo disponible más
cercano, usando cálculo espacial. Ejecutar SOLO si el distrito arroja resultado ROJO
(0 mamógrafos).
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito.

### 4. generar_mapa_cobertura
**Propósito:** Generar un mapa interactivo en formato HTML (usando folium) que ubica
el polígono del distrito evaluado y coloca marcadores en los centros de salud con
mamógrafo disponibles en la zona. Guarda el archivo HTML resultante en disco.
**Parámetros:**
- `nombre_distrito` (str, requerido): Nombre del distrito a mapear.

## Flujo de Ejecución (Workflow)
1. Siempre comienza ejecutando `cargar_bases_y_shapefile()` para cargar el estado inicial.
2. Cuando el usuario pregunte por un distrito, ejecuta `semaforizar_distrito(nombre_distrito)`.
3. Si el resultado es "🔴 SEMÁFORO ROJO", ejecuta inmediatamente
   `calcular_mamografo_cercano(nombre_distrito)` para ofrecer al usuario la alternativa
   disponible más cercana.
4. Si el usuario solicita una visualización, un mapa, o quiere "ver" la cobertura del
   distrito, ejecuta `generar_mapa_cobertura(nombre_distrito)` y comparte la ruta del
   archivo HTML generado.
5. Sintetiza los hallazgos de forma clara y en español, indicando el estado del
   semáforo, la demanda, la capacidad instalada y, si corresponde, la distancia al
   establecimiento alternativo y la ruta del mapa generado.