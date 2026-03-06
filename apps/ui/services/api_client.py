import requests


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict:
        resp = requests.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def list_projects(self) -> list[dict]:
        resp = requests.get(f"{self.base_url}/projects", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def create_project(self, name: str, description: str | None = None) -> dict:
        resp = requests.post(
            f"{self.base_url}/projects",
            json={"name": name, "description": description},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def seed_project_source(
        self,
        project_id: str,
        external_id: str,
        content: str,
        connector: str = "manual",
    ) -> dict:
        resp = requests.post(
            f"{self.base_url}/projects/{project_id}/sources",
            json={"connector": connector, "external_id": external_id, "content": content},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def chat(self, project_id: str, message: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/chat",
            json={"project_id": project_id, "message": message},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
