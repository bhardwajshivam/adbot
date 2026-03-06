import streamlit as st

from services.api_client import ApiClient

st.title("Dashboard")

api_base = st.session_state.get("api_base_url", "http://localhost:8000")
client = ApiClient(api_base)

col1, col2 = st.columns(2)

with col1:
    try:
        health = client.health()
        st.metric("API Status", health.get("status", "unknown"))
    except Exception as exc:
        st.metric("API Status", "down")
        st.caption(str(exc))

with col2:
    try:
        projects = client.list_projects()
        st.metric("Projects", len(projects))
    except Exception:
        st.metric("Projects", 0)

st.subheader("Create Project")
with st.form("create_project"):
    name = st.text_input("Name")
    description = st.text_input("Description")
    submitted = st.form_submit_button("Create", use_container_width=True)

if submitted:
    if not name.strip():
        st.warning("Project name is required.")
    else:
        try:
            created = client.create_project(name=name.strip(), description=description.strip() or None)
            st.success(f"Created project {created['name']} ({created['id'][:8]}).")
        except Exception as exc:
            st.error(f"Could not create project: {exc}")

st.subheader("Recent Projects")
try:
    projects = client.list_projects()
    if projects:
        st.dataframe(projects, use_container_width=True)
    else:
        st.info("No projects yet.")
except Exception as exc:
    st.error(f"Could not load projects: {exc}")
