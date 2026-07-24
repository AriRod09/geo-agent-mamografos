---
name: peru-mammography-analysis
description: Analyse and evaluate the coverage and access to mammography services in Peru.
---
# Peru Mammography Analysis

## Overview
This skill guides the agent to evaluate breast cancer screening coverage by crossing demographic demand with hospital installed capacity, producing a traffic-light alert (Semaforización).

## Tools Reference

### 1. cargar_bases_y_shapefile
**Purpose:** Initialize environment, clean spatial coordinates, merge UBIGEON, and download the district boundaries.
**Parameters:** None

### 2. semaforizar_distrito
**Purpose:** Evaluate the population (women 40-69) vs hospital category in a given district. Call AFTER charging databases.
**Parameters:** 
- `nombre_distrito` (str, required): The name of the Peruvian district to analyze.

### 3. calcular_mamografo_cercano
**Purpose:** Calculate the exact distance in km to the closest mammograph using spatial bounding. Call ONLY if the district returns ROJO (0 mammographs).
**Parameters:** 
- `nombre_distrito` (str, required): The name of the district.

## Workflow Execution
1. Always start by executing `cargar_bases_y_shapefile()` to load state.
2. When the user asks about a district, run `semaforizar_distrito(nombre_distrito)`.
3. If the result is "🔴 SEMÁFORO ROJO", immediately run `calcular_mamografo_cercano(nombre_distrito)` to provide the user with the closest available alternative.
4. Synthesize the findings clearly.