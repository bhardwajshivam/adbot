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

    def chat(self, project_id: str, message: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/chat",
            json={"project_id": project_id, "message": message},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
