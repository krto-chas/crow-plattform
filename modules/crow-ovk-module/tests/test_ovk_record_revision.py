"""Besiktningsposten sparas bara om sparningen utgår från det som ligger där nu."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_ovk_workflow import _client, _workflow_payload

URL = "/api/ovk/projects/p1/inspections/ovk-001"
HEADER = "X-OVK-Record-Revision"


def _named(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = _workflow_payload()
    payload["inspection"]["object"]["name"] = name
    return payload


def test_new_record_needs_no_revision_and_every_answer_carries_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)

    created = client.put(URL, json=_workflow_payload())

    assert created.status_code == 200, created.text
    revision = created.headers[HEADER]
    assert len(revision) == 64
    read = client.get(URL)
    assert read.headers[HEADER] == revision
    # Revisionen följer innehållet: samma post ger samma värde, en ändring ett nytt.
    changed = client.put(URL, json=_named("Nytt namn"), headers={"X-OVK-Base-Revision": revision})
    assert changed.status_code == 200, changed.text
    assert changed.headers[HEADER] != revision
    assert client.get(URL).headers[HEADER] == changed.headers[HEADER]


def test_stale_save_is_refused_and_nothing_is_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)
    first = client.put(URL, json=_workflow_payload()).headers[HEADER]
    # Någon annan sparar: en annan flik, eller ett nybyggt eller återställt utkast.
    other = client.put(URL, json=_named("Sparat av annan"), headers={"X-OVK-Base-Revision": first})
    assert other.status_code == 200
    stored = client.get(URL)

    stale = client.put(URL, json=_named("Gammal flik"), headers={"X-OVK-Base-Revision": first})

    assert stale.status_code == 409
    assert stale.json()["detail"] == {"code": "OVK_RECORD_REVISION_CONFLICT"}
    after = client.get(URL)
    assert after.json() == stored.json()
    assert after.headers[HEADER] == stored.headers[HEADER]
    for wrong in ("", "x" * 64, "new"):
        refused = client.put(URL, json=_named("X"), headers={"X-OVK-Base-Revision": wrong})
        assert refused.status_code == 409, wrong
    assert client.get(URL).json() == stored.json()


def test_save_without_revision_cannot_change_an_existing_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)
    assert client.put(URL, json=_workflow_payload()).status_code == 200
    stored = client.get(URL)

    blind = client.put(URL, json=_named("Skriver över"))

    # Till exempel en ny besiktning som råkar få ett ID som redan finns.
    assert blind.status_code == 428
    assert blind.json()["detail"] == {"code": "OVK_RECORD_REVISION_REQUIRED"}
    assert client.get(URL).json() == stored.json()


def test_repeating_the_same_save_without_revision_is_harmless(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)
    created = client.put(URL, json=_workflow_payload())
    assert created.status_code == 200

    # Svaret kom aldrig fram och klienten försöker igen med samma innehåll.
    again = client.put(URL, json=_workflow_payload())

    assert again.status_code == 200, again.text
    stored = client.get(URL).json()
    assert {k: v for k, v in stored.items() if k != "updated_at"} == {
        k: v for k, v in created.json().items() if k != "updated_at"
    }


def test_revision_for_a_record_that_no_longer_exists_is_a_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)

    gone = client.put(URL, json=_workflow_payload(), headers={"X-OVK-Base-Revision": "a" * 64})

    assert gone.status_code == 409
    assert gone.json()["detail"] == {"code": "OVK_RECORD_REVISION_CONFLICT"}
    assert client.get(URL).status_code == 404


def test_rebuilt_draft_makes_an_open_form_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_ovk_draft_archive import BASE, _prepared

    client, headers = _prepared(tmp_path, monkeypatch)
    url = "/api/ovk/projects/p1/inspections/ovk-utkast"
    opened = client.get(url)
    # Ett protokollutkast byggs medan formuläret står öppet.
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    built = client.get(url)
    assert built.headers[HEADER] != opened.headers[HEADER]

    stale = client.put(
        url, json=opened.json(), headers={"X-OVK-Base-Revision": opened.headers[HEADER]}
    )

    assert stale.status_code == 409
    assert client.get(url).json() == built.json()
