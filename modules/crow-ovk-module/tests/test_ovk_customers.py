"""Kundregistret och kundkopplingen på fastigheten."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from crow_ovk_fastighet import (
    Fastighet,
    FastighetRepository,
    Kund,
    KundRepository,
    fastighet_from_payload,
    fastighet_to_payload,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk_module.ovk_customer_surface import kund_revision
from crow_ovk_module.plugin import CrowOvkModulePlugin

_NEW = {"X-OVK-Base-Revision": "new"}
_FASTIGHET = "/api/ovk/projects/p1/fastighet/object-1"


def _client(root: Path) -> TestClient:
    app = FastAPI()
    for router in CrowOvkModulePlugin().routers(root):
        app.include_router(router)
    return TestClient(app)


def _create(client: TestClient, kund_id: str = "kund-1", **fields: Any) -> dict[str, Any]:
    response = client.put(
        f"/api/ovk/kunder/{kund_id}", json={"namn": "Brf Lärkan", **fields}, headers=_NEW
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_customer_is_created_listed_and_read_back(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_USER_ID", "stoffe")
    client = _client(tmp_path)

    created = _create(
        client,
        kontaktperson="Anna Ek",
        telefon="08-123 45",
        epost="styrelsen@larkan.example",
        postadress={"gata": "Storgatan 1", "postnr": "185 31", "ort": "Vaxholm"},
        referens="Avtal 2026",
    )

    assert created["kund_id"] == "kund-1"
    assert created["namn"] == "Brf Lärkan"
    assert created["postadress"] == {"gata": "Storgatan 1", "postnr": "185 31", "ort": "Vaxholm"}
    assert created["updated_by"] == "stoffe"
    assert created["updated_at"]
    assert created["revision"] == kund_revision(KundRepository(tmp_path).load("kund-1"))
    assert client.get("/api/ovk/kunder/kund-1").json() == created
    listed = client.get("/api/ovk/kunder").json()
    assert listed == {"kunder": [{**created, "antal_fastigheter": 0}], "fullstandig": True}


def test_customers_are_listed_by_name(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client, "kund-b", namn="örnen Fastigheter")
    _create(client, "kund-a", namn="Brf Lärkan")

    names = [item["namn"] for item in client.get("/api/ovk/kunder").json()["kunder"]]

    assert names == ["Brf Lärkan", "örnen Fastigheter"]


def test_saving_requires_the_revision_the_change_is_based_on(tmp_path: Path) -> None:
    client = _client(tmp_path)

    missing = client.put("/api/ovk/kunder/kund-1", json={"namn": "Brf Lärkan"})
    assert missing.status_code == 428
    assert missing.json() == {"detail": {"code": "KUND_REVISION_REQUIRED"}}
    assert not KundRepository(tmp_path).exists("kund-1")

    created = _create(client)

    again = client.put("/api/ovk/kunder/kund-1", json={"namn": "Annan"}, headers=_NEW)
    assert again.status_code == 409
    assert again.json()["detail"] == {
        "code": "KUND_REVISION_CONFLICT",
        "current_revision": created["revision"],
    }
    unknown = client.put(
        "/api/ovk/kunder/kund-2", json={"namn": "Ny"}, headers={"X-OVK-Base-Revision": "0" * 64}
    )
    assert unknown.status_code == 409
    assert unknown.json()["detail"]["current_revision"] is None


def test_concurrent_edit_does_not_overwrite_silently(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create(client)
    based_on = {"X-OVK-Base-Revision": created["revision"]}

    first = client.put(
        "/api/ovk/kunder/kund-1", json={"namn": "Brf Lärkan", "telefon": "1"}, headers=based_on
    )
    assert first.status_code == 200
    second = client.put(
        "/api/ovk/kunder/kund-1", json={"namn": "Brf Lärkan", "telefon": "2"}, headers=based_on
    )

    assert second.status_code == 409
    assert second.json()["detail"]["current_revision"] == first.json()["revision"]
    assert KundRepository(tmp_path).load("kund-1").telefon == "1"


@pytest.mark.parametrize(
    ("kund_id", "payload"),
    [
        ("kund-1", {"namn": "  "}),
        ("kund-1", {"namn": "Brf Lärkan", "epost": "inte en adress"}),
        ("kund-1", {"namn": "x" * 201}),
        ("kund-1", {"namn": "Brf Lärkan", "postadress": "Storgatan 1"}),
        ("kund.1", {"namn": "Brf Lärkan"}),
    ],
)
def test_invalid_customer_is_refused_and_not_stored(
    tmp_path: Path, kund_id: str, payload: dict[str, Any]
) -> None:
    response = _client(tmp_path).put(f"/api/ovk/kunder/{kund_id}", json=payload, headers=_NEW)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_KUND"
    assert not (tmp_path / "registry" / "kund").exists() or not list(
        (tmp_path / "registry" / "kund").glob("*.json")
    )


def test_client_cannot_set_who_changed_the_customer(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_USER_ID", "stoffe")
    created = _create(_client(tmp_path), updated_by="någon annan", updated_at="1999-01-01")

    assert created["updated_by"] == "stoffe"
    assert not created["updated_at"].startswith("1999")


def test_unknown_customer_is_not_found(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ovk/kunder/kund-9")

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "KUND_NOT_FOUND"}}


def test_property_can_point_at_a_registered_customer_only(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = {"fastighetsbeteckning": "Lärkan 4", "kund_id": "kund-1"}

    refused = client.put(_FASTIGHET, json=payload)
    assert refused.status_code == 422
    assert refused.json() == {"detail": {"code": "KUND_NOT_FOUND"}}
    assert FastighetRepository(tmp_path).list("p1") == ()

    _create(client)
    saved = client.put(_FASTIGHET, json=payload)
    assert saved.status_code == 200
    assert saved.json()["fastighet"]["kund_id"] == "kund-1"
    assert client.get("/api/ovk/kunder").json()["kunder"][0]["antal_fastigheter"] == 1


def test_client_unaware_of_customers_does_not_remove_the_link(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client)
    client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4", "kund_id": "kund-1"})

    # Fältappen och äldre formulär skickar ingen kund alls.
    client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4", "referensnr": "R-1"})
    stored = FastighetRepository(tmp_path).load("p1", "object-1")
    assert stored.kund_id == "kund-1"
    assert stored.referensnr == "R-1"

    # Ett uttryckligt null tar bort kopplingen.
    client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4", "kund_id": None})
    assert FastighetRepository(tmp_path).load("p1", "object-1").kund_id is None


def test_property_without_customer_serializes_as_before() -> None:
    plain = Fastighet(fastighet_id="object-1", project_id="p1", fastighetsbeteckning="Lärkan 4")
    assert "kund_id" not in fastighet_to_payload(plain)
    assert fastighet_from_payload(fastighet_to_payload(plain)) == plain

    linked = Fastighet(
        fastighet_id="object-1", project_id="p1", fastighetsbeteckning="Lärkan 4", kund_id="kund-1"
    )
    assert fastighet_to_payload(linked)["kund_id"] == "kund-1"
    assert fastighet_from_payload(fastighet_to_payload(linked)) == linked
    with pytest.raises(ValueError, match="kund_id"):
        Fastighet(
            fastighet_id="object-1",
            project_id="p1",
            fastighetsbeteckning="Lärkan 4",
            kund_id="../annan",
        )


def test_property_register_shows_the_customer(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client)
    client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4", "kund_id": "kund-1"})

    item = client.get("/api/ovk/fastigheter").json()["fastigheter"][0]
    assert item["kund"] == {"kund_id": "kund-1", "namn": "Brf Lärkan"}

    # Kundposten försvinner: kopplingen visas kvar utan påhittat namn.
    (tmp_path / "registry" / "kund" / "kund-1.json").unlink()
    item = client.get("/api/ovk/fastigheter").json()["fastigheter"][0]
    assert item["kund"] == {"kund_id": "kund-1", "namn": None}


def test_property_count_is_withheld_when_a_project_cannot_be_read(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client)
    client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4", "kund_id": "kund-1"})
    broken = tmp_path / "projects" / "p2" / "fastighet"
    broken.mkdir(parents=True)
    (broken / "trasig.json").write_text("{", encoding="utf-8")

    body = client.get("/api/ovk/kunder").json()

    assert body["fullstandig"] is False
    assert body["kunder"][0]["antal_fastigheter"] is None


def test_unreadable_customer_register_is_an_error_not_an_empty_list(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client)
    (tmp_path / "registry" / "kund" / "trasig.json").write_text("{", encoding="utf-8")

    response = client.get("/api/ovk/kunder")

    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "KUND_REGISTER_UNREADABLE"}}


def test_customer_routes_require_a_session_in_session_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path)
    _create(client)
    monkeypatch.setenv("CROW_AUTH_MODE", "session")

    assert client.get("/api/ovk/kunder").status_code == 401
    assert client.get("/api/ovk/kunder/kund-1").status_code == 401
    refused = client.put("/api/ovk/kunder/kund-1", json={"namn": "Annan"}, headers=_NEW)
    assert refused.status_code == 401
    assert KundRepository(tmp_path).load("kund-1").namn == "Brf Lärkan"


def test_customer_model_names_the_ordering_party() -> None:
    kund = Kund(kund_id="kund-1", namn="Brf Lärkan")
    assert kund.updated_by is None
    with pytest.raises(ValueError, match="namn"):
        Kund(kund_id="kund-1", namn="")


def test_property_page_carries_the_customer_panel(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/ovk/fastighet").text

    for element in (
        'id="kundPanel"',
        'id="kundNew"',
        'id="kundItems"',
        'id="kundForm"',
        'id="kundNamn"',
        '<select id="kund">',
    ):
        assert element in page
    assert page.index('<script src="/ovk/kunder.js">') < page.index(
        '<script src="/ovk/fastighet/app.js">'
    )
    script = client.get("/ovk/kunder.js")
    assert script.status_code == 200
    assert "/api/ovk/kunder" in script.text
    assert "X-OVK-Base-Revision" in script.text
    assert "innerHTML" not in script.text
    app_script = client.get("/ovk/fastighet/app.js").text
    assert "window.ovkCustomers?.loaded()?{kund_id:$('kund').value||null}:{}" in app_script
