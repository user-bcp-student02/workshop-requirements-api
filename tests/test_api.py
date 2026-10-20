import os
import time
from pathlib import Path

import jwt
from fastapi.testclient import TestClient

TEST_TOKEN_SECRET = "test-only-workshop-secret-with-32-bytes-minimum"
TOKEN_ISSUER = "workshop-auth-backend"
os.environ.setdefault("WORKSHOP_TOKEN_SECRET", TEST_TOKEN_SECRET)

from app.main import create_app


def token(username: str = "student", role: str = "STUDENT", expires_in: int = 3600, issuer: str = TOKEN_ISSUER) -> str:
    return jwt.encode(
        {"sub": username, "role": role, "iss": issuer, "exp": int(time.time()) + expires_in},
        TEST_TOKEN_SECRET,
        algorithm="HS256",
    )


def headers(username: str = "student", role: str = "STUDENT") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(username, role)}"}


def test_lists_seeded_tasks(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers=headers())
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_creates_task_and_summary(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        created = client.post(
            "/api/tasks",
            headers=headers(),
            json={"title": "Add tests", "description": "Improve coverage", "status": "TODO", "priority": "HIGH"},
        )
        summary = client.get("/api/summary", headers=headers())
    assert created.status_code == 201
    assert created.json()["owner"] == "student"
    assert summary.json()["total"] == 3


def test_uploads_requirement(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("requirements.txt", b"Login must be accessible", "text/plain")},
        )
    assert response.status_code == 201
    assert (upload_dir / "requirements.txt").exists()


def test_rejects_invalid_token(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_rejects_tampered_token(tmp_path: Path) -> None:
    signed = token()
    header, payload, signature = signed.split(".")
    tampered = f"{header}.{payload}.{('A' if signature[0] != 'A' else 'B')}{signature[1:]}"
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_rejects_expired_token(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": f"Bearer {token(expires_in=-1)}"})
    assert response.status_code == 401


def test_rejects_untrusted_issuer(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": f"Bearer {token(issuer='other')}"})
    assert response.status_code == 401
