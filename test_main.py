import psycopg2
import requests
from fastapi.testclient import TestClient

from backend.main import app
import backend.main as main


client = TestClient(app, raise_server_exceptions=False)


class FakeResponse:
    def __init__(self, status_code=200, data=None, json_error=False):
        self.status_code = status_code
        self._data = data
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("Invalid JSON")
        return self._data


# ============================================================
# HOME
# ============================================================

def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "FindMyTrain" in response.text


# ============================================================
# TRAIN SEARCH
# ============================================================

def test_train_search_valid():
    response = client.get("/trains/search?q=12919")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] >= 1
    assert any(item["train_number"] == "12919" for item in data["results"])


def test_train_search_empty():
    response = client.get("/trains/search?q=")
    assert response.status_code == 400
    assert response.json()["detail"] == "Search query cannot be empty"


def test_train_search_missing_query():
    response = client.get("/trains/search")
    assert response.status_code == 422


# ============================================================
# TRAIN DETAILS
# ============================================================

def test_train_details_valid():
    response = client.get("/trains/12919")
    assert response.status_code == 200

    data = response.json()
    assert data["train_number"] == "12919"
    assert data["train_name"]
    assert data["source"]["code"]
    assert data["destination"]["code"]
    assert isinstance(data["stops"], list)
    assert len(data["stops"]) > 0


def test_train_not_found():
    response = client.get("/trains/99999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Train not found"


# ============================================================
# STATION SEARCH
# ============================================================

def test_station_search_valid():
    response = client.get("/stations/search?q=RPZ")
    assert response.status_code == 200

    data = response.json()
    assert len(data["results"]) >= 1
    assert any(item["code"] == "RPZ" for item in data["results"])


def test_station_search_empty():
    response = client.get("/stations/search?q=")
    assert response.status_code == 400
    assert response.json()["detail"] == "Search query cannot be empty"


# ============================================================
# STATION SCHEDULE
# ============================================================

def test_station_trains_valid():
    response = client.get("/stations/RPZ/trains")
    assert response.status_code == 200

    data = response.json()
    assert data["station"]["code"] == "RPZ"
    assert data["station"]["name"]
    assert isinstance(data["trains"], list)
    assert len(data["trains"]) > 0


def test_station_not_found():
    response = client.get("/stations/ZZZZ/trains")
    assert response.status_code == 404
    assert response.json()["detail"] == "Station not found or no trains found"


# ============================================================
# LIVE TRAIN - MOCKED
# These tests do NOT call RailRadar, so they do not consume API quota.
# ============================================================

def test_live_train_success(monkeypatch):
    fake_data = {
        "success": True,
        "data": {
            "trainNumber": "12919",
            "status": "running"
        }
    }

    def fake_get(*args, **kwargs):
        return FakeResponse(200, fake_data)

    monkeypatch.setattr(main.requests, "get", fake_get)

    response = client.get("/trains/12919/live")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["trainNumber"] == "12919"


def test_live_train_timeout(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(main.requests, "get", fake_get)

    response = client.get("/trains/12919/live")

    assert response.status_code == 504
    assert response.json()["detail"] == "RailRadar request timed out"


def test_live_train_unauthorized(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(401, {"success": False})

    monkeypatch.setattr(main.requests, "get", fake_get)

    response = client.get("/trains/12919/live")

    assert response.status_code == 401
    assert response.json()["detail"] == "RailRadar API key is invalid or expired"


# ============================================================
# LIVE STATION - MOCKED
# ============================================================

def test_live_station_success(monkeypatch):
    fake_data = {
        "success": True,
        "data": {
            "station": {
                "code": "RPZ",
                "name": "Rana Pratap Nagar"
            },
            "trains": []
        }
    }

    def fake_get(*args, **kwargs):
        return FakeResponse(200, fake_data)

    monkeypatch.setattr(main.requests, "get", fake_get)

    response = client.get("/stations/RPZ/live")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["station"]["code"] == "RPZ"


def test_live_station_invalid_json(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(200, json_error=True)

    monkeypatch.setattr(main.requests, "get", fake_get)

    response = client.get("/stations/RPZ/live")

    assert response.status_code == 502
    assert response.json()["detail"] == "RailRadar returned an invalid response"


# ============================================================
# ERROR HANDLING
# ============================================================

def test_database_error(monkeypatch):
    def database_failure():
        raise psycopg2.Error("Test database failure")

    monkeypatch.setattr(main, "get_db_cursor", database_failure)

    response = client.get("/trains/search?q=12919")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database service is temporarily unavailable"


def test_unexpected_server_error(monkeypatch):
    def unexpected_failure():
        raise RuntimeError("Test unexpected failure")

    monkeypatch.setattr(main, "get_db_cursor", unexpected_failure)

    response = client.get("/trains/search?q=12919")

    assert response.status_code == 500
    assert response.json()["error"] == "Internal server error"


def test_unknown_route():
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
