import streamlit as st
from streamlit_folium import st_folium
import uuid
import tools
from tools import get_session_data
# IMPORTANTE: Asegúrate de importar tu agente correctamente
# Si tu agente está definido en un archivo llamado agent.py, usa eso.
# Si lo definiste en el notebook, tendrás que pasarlo a un script agent.py
from agent import agent

def generate_response(input_text, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    prior_state = agent.get_state(config)
    prior_count = len(prior_state.values.get("messages", [])) if prior_state.values else 0

    # Ejecutar el agente
    response = agent.invoke(
        {"messages": [{"role": "user", "content": input_text}]},
        config=config
    )

    new_messages = response["messages"][prior_count:]
    tool_calls = _pair_tool_calls(new_messages)
    return response, tool_calls

def _pair_tool_calls(messages):
    """Empareja las llamadas a las tools con sus resultados para el monitor[cite: 6]"""
    calls = []
    pending = {}
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            pending[tc["id"]] = {"tool": tc["name"], "args": tc["args"]}
        if type(m).__name__ == "ToolMessage":
            call = pending.get(m.tool_call_id, {"tool": getattr(m, "name", "?"), "args": {}})
            calls.append({**call, "result": m.content})
    return calls

def render_monitor(tool_calls):
    with st.expander("🔍 Monitor del agente (Tools ejecutadas)"):
        if tool_calls:
            st.table(tool_calls)
        else:
            st.caption("No se ejecutaron tools en este turno.")

def render_resultado_estructurado(resultado, cercanos, recomendacion):
    """Renderiza el output estructurado (semáforo + ranking de cercanos +
    recomendación final) como tarjetas/tabla/callout, complementando la
    respuesta conversacional del agente."""
    if not resultado and not cercanos and not recomendacion:
        return
    if resultado:
        col1, col2, col3 = st.columns(3)
        col1.metric("Distrito", resultado.get("distrito", "-"))
        col2.metric("Afiliadas objetivo", f"{resultado.get('demanda_afiliadas', 0):,}")
        col3.metric("Capacidad instalada", f"{resultado.get('capacidad_instalada', 0):,}")
        st.caption(resultado.get("semaforo", ""))
    if cercanos:
        st.markdown("**Ranking de establecimientos más cercanos:**")
        st.dataframe(
            cercanos,
            column_config={
                "ranking": "#",
                "establecimiento": "Establecimiento",
                "nivel_atencion": "Nivel de atención",
                "categoria": "Categoría RENIPRESS",
                "distancia_km": "Distancia (km)",
            },
            hide_index=True,
            width="stretch",
        )
    if recomendacion:
        urgencia = recomendacion.get("urgencia", "")
        texto = f"**Recomendación ({urgencia}):** {recomendacion.get('accion_recomendada', '')}"
        if urgencia == "ALTA":
            st.error(texto)
        elif urgencia == "MEDIA":
            st.warning(texto)
        else:
            st.success(texto)

@st.cache_resource
def inicializar_datos():
    """Carga las bases una sola vez por proceso, para que el Mapa Nacional esté
    disponible aunque el usuario todavía no haya conversado con el agente."""
    return tools.cargar_bases_y_shapefile()

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Geo-Agente: Mamógrafos en Perú 🏥", layout="wide")
st.title("Asistente de Cobertura de Mamografías 🏥🗺️")

inicializar_datos()

with st.sidebar:
    st.header("Configuración")
    show_monitor = st.checkbox("🔍 Mostrar monitor del agente", value=True)
    st.caption("Visualiza qué herramientas de análisis espacial está utilizando el agente en tiempo real.")

tab_chat, tab_mapa_nacional = st.tabs(["💬 Asistente", "🗺️ Mapa Nacional de Centros"])

# --- PESTAÑA: MAPA NACIONAL (siempre visible, sin necesidad de chatear) ---
with tab_mapa_nacional:
    st.subheader("Cobertura nacional de centros con mamógrafo")
    gdf_mamo_full = get_session_data()["gdf_mamo"]
    categorias_disponibles = sorted(gdf_mamo_full["CATEGORIA"].unique().tolist())
    categorias_sel = st.multiselect(
        "Filtrar por nivel de atención (categoría RENIPRESS)",
        categorias_disponibles,
        default=categorias_disponibles,
    )
    st.caption(
        f"Mostrando {len(gdf_mamo_full[gdf_mamo_full['CATEGORIA'].isin(categorias_sel)])} "
        f"de {len(gdf_mamo_full)} establecimientos con mamógrafo a nivel nacional."
    )
    mapa_nacional = tools.generar_mapa_nacional(categorias_sel or None)
    st_folium(mapa_nacional, width=None, height=550, returned_objects=[], key="mapa_nacional")

# --- PESTAÑA: CHAT CON EL AGENTE ---
with tab_chat:
    # Inicializar historial y thread_id[cite: 6]
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    # Mostrar mensajes anteriores[cite: 6]
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_resultado_estructurado(
                message.get("resultado_estructurado"),
                message.get("cercanos_estructurado"),
                message.get("recomendacion_estructurada"),
            )
            if "map" in message:
                st_folium(message["map"], width=700, height=500, returned_objects=[], key=f"map_hist_{i}")
            if show_monitor and "tool_calls" in message:
                render_monitor(message.get("tool_calls", []))

    # --- INPUT DEL USUARIO ---
    if prompt := st.chat_input("Ej: Evalúa el distrito de Chalhuanca y genera un mapa..."):

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizando bases de datos espaciales..."):
                response, tool_calls = generate_response(prompt, st.session_state.thread_id)
                content = response["messages"][-1].content

                # Manejar el formato de la respuesta[cite: 6]
                if isinstance(content, str):
                    response_text = content
                else:
                    response_text = content[0]['text']

                st.markdown(response_text)

                if show_monitor:
                    render_monitor(tool_calls)

                # --- RENDERIZAR OUTPUT ESTRUCTURADO Y MAPA SI SE GENERARON ---
                session_data = get_session_data()
                pending_map = session_data.pop("pending_map", None)
                map_title = session_data.pop("map_title", None)
                resultado_estructurado = session_data.get("ultimo_resultado")
                cercanos_estructurado = session_data.get("ultimo_cercanos")
                recomendacion_estructurada = session_data.get("ultima_recomendacion")

                render_resultado_estructurado(
                    resultado_estructurado, cercanos_estructurado, recomendacion_estructurada
                )

                assistant_message = {
                    "role": "assistant",
                    "content": response_text,
                    "tool_calls": tool_calls,
                    "resultado_estructurado": resultado_estructurado,
                    "cercanos_estructurado": cercanos_estructurado,
                    "recomendacion_estructurada": recomendacion_estructurada,
                }

                if pending_map is not None:
                    if map_title:
                        st.subheader(map_title)
                    # Renderizar el mapa de Folium directamente en Streamlit[cite: 6]
                    st_folium(pending_map, width=700, height=500, returned_objects=[], key="map_new")
                    assistant_message["map"] = pending_map

                st.session_state.messages.append(assistant_message)
