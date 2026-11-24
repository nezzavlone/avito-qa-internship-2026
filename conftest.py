from __future__ import annotations

import re
import uuid

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://qa-internship.avito.com"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        other=5,
        backoff_factor=1,
        status_forcelist=(502, 503, 504),
        allowed_methods=None,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def random_credentials() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:10]
    return f"qa_{suffix}", f"Pass_{suffix}"


def make_item_payload(seller_id: int, **overrides) -> dict:
    payload = {
        "sellerID": seller_id,
        "name": f"qa-item-{uuid.uuid4().hex[:8]}",
        "price": 9900,
        "statistics": {"likes": 21, "viewCount": 11, "contacts": 43},
    }
    payload.update(overrides)
    return payload


def extract_item_id(response: requests.Response) -> str | None:
    try:
        status_text = str(response.json().get("status", ""))
    except ValueError:
        return None
    match = UUID_RE.search(status_text)
    return match.group(0) if match else None


@pytest.fixture(scope="session")
def session() -> requests.Session:
    return make_session()


@pytest.fixture
def register_user(session):
    def _create() -> dict:
        username, password = random_credentials()
        reg = session.post(
            f"{BASE_URL}/api/1/register",
            json={"username": username, "password": password},
            timeout=15,
        )
        assert reg.status_code == 201, f"Ошибка регистрации: {reg.status_code} {reg.text}"

        auth = session.post(
            f"{BASE_URL}/api/1/autorize",
            json={"username": username, "password": password},
            timeout=15,
        )
        assert auth.status_code == 200, f"Ошибка авторизации: {auth.status_code} {auth.text}"
        token = auth.json()["accessToken"]

        return {
            "id": reg.json()["id"],
            "username": username,
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return _create


@pytest.fixture
def auth_user(register_user) -> dict:
    return register_user()


@pytest.fixture
def cleanup_items(session):
    to_delete: list[tuple[str, dict]] = []

    def _register(item_id: str | None, headers: dict) -> None:
        if item_id:
            to_delete.append((item_id, headers))

    yield _register

    for item_id, headers in to_delete:
        session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers, timeout=15)


@pytest.fixture
def created_item(session, auth_user, cleanup_items) -> dict:
    payload = make_item_payload(auth_user["id"])
    resp = session.post(
        f"{BASE_URL}/api/1/item",
        json=payload,
        headers=auth_user["headers"],
        timeout=15,
    )
    assert resp.status_code == 200, f"Не удалось создать объявление: {resp.status_code} {resp.text}"
    item_id = extract_item_id(resp)
    assert item_id, f"В ответе нет UUID объявления: {resp.text}"
    cleanup_items(item_id, auth_user["headers"])
    return {"id": item_id, "payload": payload, "user": auth_user}


@pytest.fixture(scope="module")
def shared_item(session) -> dict:
    username, password = random_credentials()
    reg = session.post(
        f"{BASE_URL}/api/1/register", json={"username": username, "password": password}, timeout=15
    )
    assert reg.status_code == 201
    auth = session.post(
        f"{BASE_URL}/api/1/autorize", json={"username": username, "password": password}, timeout=15
    )
    assert auth.status_code == 200
    headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    payload = make_item_payload(reg.json()["id"])
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=headers, timeout=15)
    assert resp.status_code == 200
    item_id = extract_item_id(resp)
    assert item_id

    yield {"id": item_id, "payload": payload, "user": {"id": reg.json()["id"], "headers": headers}}

    session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers, timeout=15)
