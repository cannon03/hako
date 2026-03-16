# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


# We use the TestClient inside a 'with' block to trigger the lifespan events
# This ensures your directories and SQLite tables are created before the tests run!
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_bucket(client):
    response = client.put("/buckets/pytest-bucket")
    # 201 Created or 409 Conflict (if it already exists from a previous test run)
    assert response.status_code in [201, 409]


def test_upload_object(client):
    file_content = b"Hello, Content-Addressed Storage!"
    response = client.put(
        "/objects/pytest-bucket/test-folder/hello.txt", content=file_content
    )
    assert response.status_code == 200
    assert "hash" in response.json()
    assert response.json()["size"] == len(file_content)


def test_download_object(client):
    response = client.get("/objects/pytest-bucket/test-folder/hello.txt")
    assert response.status_code == 200
    assert response.content == b"Hello, Content-Addressed Storage!"
    assert "Accept-Ranges" in response.headers


def test_delete_bucket_fails_if_not_empty(client):
    # Should fail because we just uploaded hello.txt
    response = client.delete("/buckets/pytest-bucket")
    assert response.status_code == 400  # Or 409, depending on your exact error code


def test_delete_object(client):
    response = client.delete("/objects/pytest-bucket/test-folder/hello.txt")
    assert response.status_code == 204


def test_delete_bucket_succeeds(client):
    # Now that the object is deleted, the bucket deletion should succeed
    response = client.delete("/buckets/pytest-bucket")
    assert response.status_code == 204
