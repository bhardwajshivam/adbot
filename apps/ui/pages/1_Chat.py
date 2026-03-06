import streamlit as st

from services.api_client import ApiClient

st.title("Chat")

api_base = st.session_state.get("api_base_url", "http://localhost:8000")
client = ApiClient(api_base)

project_id = st.text_input("Project ID")
message = st.text_area("Message", height=160)

if st.button("Send", use_container_width=True):
    if not message.strip():
        st.warning("Enter a message before sending.")
    else:
        try:
            result = client.chat(project_id=project_id, message=message)
            st.success(result.get("response", "No response body"))
        except Exception as exc:
            st.error(f"Request failed: {exc}")
