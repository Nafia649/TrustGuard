def test_health_check(client):
    """Test health check returns HTTP 200 and expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "trustguard-backend"
    assert "demo_mode" in data


def test_root_endpoint(client):
    """Test root endpoint redirects/informs about docs."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "/docs" in data["docs_url"]
