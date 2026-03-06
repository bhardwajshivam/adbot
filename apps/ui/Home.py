import os

import streamlit as st

st.set_page_config(page_title="Adbot", layout="wide")

st.title("Adbot")
st.caption("Admin chatbot for project-aware retrieval and recommendations")

default_api = os.getenv("API_BASE_URL", "http://localhost:8000")
api_base = st.text_input("API base URL", value=default_api)
st.session_state["api_base_url"] = api_base

st.markdown("Use the left navigation to open Chat and Dashboard.")
