import streamlit as st
from streamlit_folium import st_folium
import uuid
from tools import get_session_data
# IMPORTANTE: Asegúrate de importar tu agente correctamente
# Si tu agente está definido en un archivo llamado agent.py, usa eso.
# Si lo definiste en el notebook, tendrás que pasarlo a un script agent.py
from agent import agent 
from tools import get_session_data

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

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Geo-Agente: Mamógrafos en Perú 🏥", layout="wide")
st.title("Asistente de Cobertura de Mamografías 🏥🗺️")

with st.sidebar:
    st.header("Configuración")
    show_monitor = st.checkbox("🔍 Mostrar monitor del agente", value=True)
    st.caption("Visualiza qué herramientas de análisis espacial está utilizando el agente en tiempo real.")

# Inicializar historial y thread_id[cite: 6]
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Mostrar mensajes anteriores[cite: 6]
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "map" in message:
            st_folium(message["map"], width=700, height=500, returned_objects=[])
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

            # --- RENDERIZAR MAPA SI SE GENERÓ UNO ---
            session_data = get_session_data()
            pending_map = session_data.pop("pending_map", None)
            map_title = session_data.pop("map_title", None)

            assistant_message = {
                "role": "assistant",
                "content": response_text,
                "tool_calls": tool_calls,
            }

            if pending_map is not None:
                if map_title:
                    st.subheader(map_title)
                # Renderizar el mapa de Folium directamente en Streamlit[cite: 6]
                st_folium(pending_map, width=700, height=500, returned_objects=[])
                assistant_message["map"] = pending_map

            st.session_state.messages.append(assistant_message)