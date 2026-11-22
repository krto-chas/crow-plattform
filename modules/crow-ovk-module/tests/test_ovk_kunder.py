"""Kundregistret och kundkopplingen på fastigheten."""

from __future__ import annotations

import json
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
from test_ovk_overview_surface import _entitle

from crow_ovk_module.ovk_kund_surface import kund_revision
from crow_ovk_module.plugin import CrowOvkModulePlugin
from crow_workbench.shell import create_app

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


def test_kund_is_created_listed_and_read_back(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
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
    assert listed == {
        "kunder": [{**created, "antal_fastigheter": 0}],
        "ej_lasbara": [],
        "antal_fastigheter_kant": True,
        "fullstandig": True,
    }


def test_kunder_are_listed_by_name(tmp_path: Path) -> None:
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
        ("kund-1", {"namn": None}),
        ("kund-1", {"namn": {"a": 1}}),
        ("kund-1", {"namn": "Brf Lärkan", "telefon": 81234}),
        ("kund-1", {"namn": "Brf Lärkan", "referens": "rad 1\nrad 2"}),
        ("kund-1", {"namn": "Brf Lärkan", "postadress": {"gata": "x" * 201}}),
        ("kund-1", {"namn": "Brf Lärkan", "postadress": {"ort": None, "gata": 5}}),
        ("kund.1", {"namn": "Brf Lärkan"}),
        (" kund-1", {"namn": "Brf Lärkan"}),
        ("kund-1", {"namn": "Brf Lärkan", "postadress": {"gata": "rad 1\nrad 2"}}),
    ],
)
def test_invalid_kund_is_refused_and_not_stored(
    tmp_path: Path, kund_id: str, payload: dict[str, Any]
) -> None:
    response = _client(tmp_path).put(f"/api/ovk/kunder/{kund_id}", json=payload, headers=_NEW)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_KUND"
    assert not (tmp_path / "registry" / "kund").exists() or not list(
        (tmp_path / "registry" / "kund").glob("*.json")
    )


def test_client_cannot_set_who_changed_the_kund(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_USER_ID", "stoffe")
    created = _create(_client(tmp_path), updated_by="någon annan", updated_at="1999-01-01")

    assert created["updated_by"] == "stoffe"
    assert not created["updated_at"].startswith("1999")


def test_unknown_kund_is_not_found(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ovk/kunder/kund-9")

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "KUND_NOT_FOUND"}}


def test_property_can_point_at_a_registered_kund_only(tmp_path: Path) -> None:
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


def test_client_unaware_of_kunder_does_not_remove_the_link(tmp_path: Path) -> None:
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


def test_property_without_kund_serializes_as_before() -> None:
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


def test_property_register_shows_the_kund(tmp_path: Path) -> None:
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
    assert body["antal_fastigheter_kant"] is False
    assert body["ej_lasbara"] == []
    assert body["kunder"][0]["antal_fastigheter"] is None


def test_one_unreadable_kund_does_not_hide_the_others(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create(client)
    registry = tmp_path / "registry" / "kund"
    (registry / "trasig.json").write_text("{", encoding="utf-8")
    # En läsbar post som säger sig vara en annan kund än filen den ligger i.
    (registry / "fel-namn.json").write_text(
        (registry / "kund-1.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    body = client.get("/api/ovk/kunder").json()

    assert [item["kund_id"] for item in body["kunder"]] == ["kund-1"]
    assert body["ej_lasbara"] == ["fel-namn", "trasig"]
    assert body["fullstandig"] is False
    assert body["antal_fastigheter_kant"] is True

    # Den trasiga posten skrivs inte över, och felet skylls inte på indata.
    for revision in ("new", created["revision"]):
        refused = client.put(
            "/api/ovk/kunder/trasig",
            json={"namn": "Ny"},
            headers={"X-OVK-Base-Revision": revision},
        )
        assert refused.status_code == 409
        assert refused.json() == {"detail": {"code": "KUND_UNREADABLE"}}
    assert (registry / "trasig.json").read_text(encoding="utf-8") == "{"
    assert client.get("/api/ovk/kunder/trasig").status_code == 409


def test_null_and_missing_optional_fields_are_empty_not_the_text_none(tmp_path: Path) -> None:
    created = _create(_client(tmp_path), namn="  Brf Lärkan  ", telefon=None, postadress=None)

    assert created["namn"] == "Brf Lärkan"
    assert created["telefon"] == ""
    assert created["kontaktperson"] == ""
    assert created["postadress"] == {"gata": "", "postnr": "", "ort": ""}


def test_unreadable_previous_property_can_still_be_overwritten(tmp_path: Path) -> None:
    client = _client(tmp_path)
    path = tmp_path / "projects" / "p1" / "fastighet" / "object-1.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")

    saved = client.put(_FASTIGHET, json={"fastighetsbeteckning": "Lärkan 4"})

    assert saved.status_code == 200
    assert FastighetRepository(tmp_path).load("p1", "object-1").kund_id is None


def test_shell_refuses_kund_routes_without_an_ovk_licence(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    _entitle(tmp_path, active=False)
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/ovk/kunder").status_code == 403
    refused = client.put("/api/ovk/kunder/kund-1", json={"namn": "Brf Lärkan"}, headers=_NEW)
    assert refused.status_code == 403
    assert not (tmp_path / "registry" / "kund").exists()


def test_kund_routes_require_a_session_in_session_mode(
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


def test_kund_model_names_the_ordering_party() -> None:
    kund = Kund(kund_id="kund-1", namn="Brf Lärkan")
    assert kund.updated_by is None
    with pytest.raises(ValueError, match="namn"):
        Kund(kund_id="kund-1", namn="")


def test_property_page_carries_the_kund_panel(tmp_path: Path) -> None:
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
    assert "window.ovkKunder?.loaded()?{kund_id:$('kund').value||null}:{}" in app_script
    # ADR-013: beställaren heter kund i identifierare, inte customer.
    assert "customer" not in script.text.lower()


@pytest.mark.parametrize(
    "written",
    ["212000-0142", "2120000142", " 212000 0142 ", "162120000142"],
)
def test_organisationsnummer_is_optional_and_stored_in_one_form(
    tmp_path: Path, written: str
) -> None:
    client = _client(tmp_path)

    created = _create(client, organisationsnummer=written)

    assert created["organisationsnummer"] == "212000-0142"
    assert client.get("/api/ovk/kunder/kund-1").json()["organisationsnummer"] == "212000-0142"


@pytest.mark.parametrize(
    "written",
    ["212000-0143", "12345", "212000-01420", "abc", "２１２０００-０１４２", 2120000142],
)
def test_wrong_organisationsnummer_is_refused(tmp_path: Path, written: Any) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/kunder/kund-1",
        json={"namn": "Brf Lärkan", "organisationsnummer": written},
        headers=_NEW,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_KUND"
    assert not KundRepository(tmp_path).exists("kund-1")


def test_kund_without_organisationsnummer_is_stored_as_before(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = _create(client, organisationsnummer="")

    assert "organisationsnummer" not in created
    stored = json.loads((tmp_path / "registry" / "kund" / "kund-1.json").read_text("utf-8"))
    assert "organisationsnummer" not in stored
    # Numret kan läggas till och tas bort igen utan att annat ändras.
    added = client.put(
        "/api/ovk/kunder/kund-1",
        json={"namn": "Brf Lärkan", "organisationsnummer": "212000-0142"},
        headers={"X-OVK-Base-Revision": created["revision"]},
    ).json()
    assert added["organisationsnummer"] == "212000-0142"
    removed = client.put(
        "/api/ovk/kunder/kund-1",
        json={"namn": "Brf Lärkan"},
        headers={"X-OVK-Base-Revision": added["revision"]},
    ).json()
    assert "organisationsnummer" not in removed


def test_organisationsnummer_message_names_the_field(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/kunder/kund-1",
        json={"namn": "Brf Lärkan", "organisationsnummer": "212000-0143"},
        headers=_NEW,
    )

    assert "organisationsnummer" in response.json()["detail"]["message"]
    assert Kund(kund_id="kund-1", namn="Brf Lärkan").organisationsnummer == ""
