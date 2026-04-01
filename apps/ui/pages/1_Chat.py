import streamlit as st

from services.api_client import ApiClient

st.title("Chat")

api_base = st.session_state.get("api_base_url", "http://localhost:8000")
client = ApiClient(api_base)

try:
    projects = client.list_projects()
except Exception as exc:
    projects = []
    st.error(f"Could not load projects: {exc}")

if not projects:
    st.info("Create a project in Dashboard first.")
    st.stop()

project_options = {f"{p['name']} ({p['id'][:8]})": p["id"] for p in projects}
selected_label = st.selectbox("Project", list(project_options.keys()))
project_id = project_options[selected_label]

with st.expander("Seed Context"):
    external_id = st.text_input("External ID", value="manual-note-1")
    content = st.text_area("Source Content", height=120)
    if st.button("Add Context", use_container_width=True):
        if not content.strip():
            st.warning("Enter source content before adding.")
        else:
            try:
                seeded = client.seed_project_source(project_id, external_id, content)
                st.success(f"Added chunk {seeded['chunk_id'][:8]} for this project.")
            except Exception as exc:
                st.error(f"Could not add context: {exc}")

message = st.text_area("Message", height=160)

if st.button("Send", use_container_width=True):
    if not message.strip():
        st.warning("Enter a message before sending.")
    else:
        try:
            result = client.chat(project_id=project_id, message=message)
            st.success(result.get("response", "No response body"))
            matches = result.get("matches", [])
            if matches:
                st.subheader("Matched Context")
                for idx, match in enumerate(matches, start=1):
                    st.markdown(
                        f"**{idx}.** `{match['chunk_id']}` "
                        f"(doc `{match['doc_id']}`, rank {match['original_rank']} -> {match['reranked_rank']})"
                    )
                    st.caption(
                        f"retrieval={match['retrieval_score']:.2f}, reranker={match['reranker_score']:.4f}"
                    )
                    st.write(match["text"])
        except Exception as exc:
            st.error(f"Request failed: {exc}")
