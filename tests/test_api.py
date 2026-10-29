from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import create_app


@pytest.fixture

def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = create_app(engine=engine, serial_enabled=False)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def test_create_list_update_delete_shipment(client: TestClient) -> None:
    instruments = client.get("/api/instruments").json()
    assert len(instruments) >= 1
    instrument = instruments[0]

    created = client.post("/api/shipments", json={"instrument_id": instrument["id"], "value": 10.0})
    assert created.status_code == 201
    shipment = created.json()
    assert shipment["arinc_word"] > 0
    assert shipment["arinc_hex"].startswith("0x")
    assert shipment["instrument_name"] == instrument["name"]
    assert shipment["min_value"] == instrument["min_value"]
    assert shipment["max_value"] == instrument["max_value"]

    listed = client.get("/api/shipments")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/api/shipments/{shipment['id']}",
        json={"instrument_id": instrument["id"], "value": 20.0},
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == 20.0

    deleted = client.delete(f"/api/shipments/{shipment['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/shipments").json() == []


def test_homepage_serves_crud_interface(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Gestor de envíos" in response.text
    assert "RANGO MÍN.—MÁX." in response.text
    assert client.get("/static/app.js").status_code == 200


def test_rejects_out_of_range_value(client: TestClient) -> None:
    instrument = client.get("/api/instruments").json()[0]
    response = client.post(
        "/api/shipments",
        json={"instrument_id": instrument["id"], "value": instrument["max_value"] + 1},
    )
    assert response.status_code == 422


def test_transmit_requires_hardware_to_be_enabled(client: TestClient) -> None:
    instrument = client.get("/api/instruments").json()[0]
    shipment = client.post("/api/shipments", json={"instrument_id": instrument["id"], "value": 1})
    response = client.post(f"/api/shipments/{shipment.json()['id']}/transmit")
    assert response.status_code == 409


def test_create_transmits_word_when_hardware_is_enabled() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = create_app(engine=engine, serial_enabled=True)
    with patch("app.main.send_word", return_value=4) as send:
        with TestClient(app) as test_client:
            instrument = test_client.get("/api/instruments").json()[0]
            response = test_client.post(
                "/api/shipments", json={"instrument_id": instrument["id"], "value": 10.0}
            )

    assert response.status_code == 201
    shipment = response.json()
    send.assert_called_once()
    assert send.call_args.args[2] == shipment["arinc_word"]
    assert shipment["transmitted_at"] is not None
    engine.dispose()


def test_update_transmits_regenerated_word_when_hardware_is_enabled() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = create_app(engine=engine, serial_enabled=True)
    with patch("app.main.send_word", return_value=4) as send:
        with TestClient(app) as test_client:
            instrument = test_client.get("/api/instruments").json()[0]
            created = test_client.post(
                "/api/shipments", json={"instrument_id": instrument["id"], "value": 10.0}
            )
            send.reset_mock()
            updated = test_client.put(
                f"/api/shipments/{created.json()['id']}",
                json={"instrument_id": instrument["id"], "value": 20.0},
            )

    assert updated.status_code == 200
    assert updated.json()["value"] == 20.0
    assert updated.json()["transmitted_at"] is not None
    send.assert_called_once()
    assert send.call_args.args[2] == updated.json()["arinc_word"]
    engine.dispose()
