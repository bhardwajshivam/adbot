def test_create_and_list_projects(client):
    create_response = client.post(
        "/projects",
        json={"name": "Project Alpha", "description": "Initial project"},
    )
    assert create_response.status_code == 201

    created = create_response.json()
    assert created["name"] == "Project Alpha"
    assert created["description"] == "Initial project"

    list_response = client.get("/projects")
    assert list_response.status_code == 200

    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["id"] == created["id"]


def test_seed_and_chat_returns_matches(client):
    create_response = client.post(
        "/projects",
        json={"name": "Project Beta", "description": "Has indexed context"},
    )
    project_id = create_response.json()["id"]

    seed_response = client.post(
        f"/projects/{project_id}/sources",
        json={
            "connector": "manual",
            "external_id": "doc-1",
            "content": "Q4 budget was reduced by 12 percent for marketing operations.",
        },
    )
    assert seed_response.status_code == 201

    chat_response = client.post(
        "/chat",
        json={"project_id": project_id, "message": "What changed in Q4 budget?"},
    )
    assert chat_response.status_code == 200

    body = chat_response.json()
    assert "Project 'Project Beta' context:" in body["response"]
    assert len(body["matches"]) >= 1
    assert "budget" in body["matches"][0]["snippet"].lower()


def test_chat_returns_404_for_missing_project(client):
    response = client.post(
        "/chat",
        json={"project_id": "does-not-exist", "message": "Hello"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
