import uuid

import allure
import pytest

from conftest import BASE_URL, extract_item_id, make_item_payload, random_credentials


def assert_item_fields(actual: dict, expected_payload: dict, expected_id: str) -> None:
    assert actual["id"] == expected_id
    assert actual["sellerId"] == expected_payload["sellerID"]
    assert actual["name"] == expected_payload["name"]
    assert actual["price"] == expected_payload["price"]
    assert actual["statistics"] == expected_payload["statistics"]
    assert actual.get("createdAt"), "Поле createdAt должно быть заполнено"


@allure.title("TC-REG-01: Успешная регистрация нового пользователя")
def test_register_success(session):
    username, password = random_credentials()
    resp = session.post(f"{BASE_URL}/api/1/register", json={"username": username, "password": password})

    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body["id"], int)
    assert body["id"] > 0
    assert body["username"] == username


@allure.title("TC-REG-02: Повторная регистрация существующего username возвращает 409")
def test_register_duplicate(session):
    username, password = random_credentials()
    first = session.post(f"{BASE_URL}/api/1/register", json={"username": username, "password": password})
    assert first.status_code == 201

    second = session.post(
        f"{BASE_URL}/api/1/register", json={"username": username, "password": "OtherPassword1"}
    )
    assert second.status_code == 409


@allure.title("TC-REG-03: Регистрация с некорректным телом запроса возвращает 400 ({case})")
@pytest.mark.parametrize(
    ("case", "body"),
    [
        ("пустой объект", {}),
        ("без username", {"password": "Pass_12345"}),
        ("без password", {"username": f"qa_{uuid.uuid4().hex[:6]}"}),
        ("пустой username", {"username": "", "password": "Pass_12345"}),
        ("пустой password", {"username": f"qa_{uuid.uuid4().hex[:6]}", "password": ""}),
        ("username из пробелов", {"username": "   ", "password": "Pass_12345"}),
    ],
)
def test_register_invalid_body(session, case, body):
    resp = session.post(f"{BASE_URL}/api/1/register", json=body)
    assert resp.status_code == 400, f"{case}: ожидали 400, получили {resp.status_code} ({resp.text})"


@allure.title("TC-AUTH-01: Успешная авторизация возвращает Bearer JWT-токен")
def test_authorize_success(session):
    username, password = random_credentials()
    session.post(f"{BASE_URL}/api/1/register", json={"username": username, "password": password})

    resp = session.post(f"{BASE_URL}/api/1/autorize", json={"username": username, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokenType"] == "Bearer"
    assert body["accessToken"].count(".") == 2


@allure.title("TC-AUTH-02: Авторизация с неверным паролем возвращает 401")
def test_authorize_wrong_password(session, auth_user):
    resp = session.post(
        f"{BASE_URL}/api/1/autorize",
        json={"username": auth_user["username"], "password": "wrong_password"},
    )
    assert resp.status_code == 401


@allure.title("TC-AUTH-03: Авторизация несуществующего пользователя возвращает 401")
def test_authorize_unknown_user(session):
    username, password = random_credentials()
    resp = session.post(f"{BASE_URL}/api/1/autorize", json={"username": username, "password": password})
    assert resp.status_code == 401


@allure.title("TC-AUTH-04: Авторизация с пустыми полями возвращает 400")
@pytest.mark.parametrize("body", [{}, {"username": "", "password": ""}])
def test_authorize_invalid_body(session, body):
    resp = session.post(f"{BASE_URL}/api/1/autorize", json=body)
    assert resp.status_code == 400


@allure.title(
    "TC-ACC-01: Защищённые ручки без валидного Bearer-токена возвращают 401 ({endpoint}, {auth_case})"
)
@pytest.mark.parametrize(
    ("auth_case", "headers"),
    [
        ("без заголовка", {}),
        ("невалидный токен", {"Authorization": "Bearer invalid.jwt.token"}),
        ("подмена через X-UserId", {"X-UserId": "1"}),
    ],
)
@pytest.mark.parametrize(
    "endpoint",
    [
        "POST /api/1/item",
        "GET /api/1/item/{id}",
        "GET /api/1/{sellerID}/item",
        "GET /api/1/statistic/{id}",
        "GET /api/2/statistic/{id}",
        "DELETE /api/2/item/{id}",
    ],
)
def test_protected_endpoints_require_auth(session, shared_item, endpoint, auth_case, headers):
    item_id = shared_item["id"]
    seller_id = shared_item["user"]["id"]

    if endpoint == "POST /api/1/item":
        resp = session.post(f"{BASE_URL}/api/1/item", json=shared_item["payload"], headers=headers)
    elif endpoint == "GET /api/1/item/{id}":
        resp = session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=headers)
    elif endpoint == "GET /api/1/{sellerID}/item":
        resp = session.get(f"{BASE_URL}/api/1/{seller_id}/item", headers=headers)
    elif endpoint == "GET /api/1/statistic/{id}":
        resp = session.get(f"{BASE_URL}/api/1/statistic/{item_id}", headers=headers)
    elif endpoint == "GET /api/2/statistic/{id}":
        resp = session.get(f"{BASE_URL}/api/2/statistic/{item_id}", headers=headers)
    else:
        resp = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)

    assert resp.status_code == 401, f"{endpoint} ({auth_case}): ожидали 401, получили {resp.status_code}"


@allure.title("TC-CR-01: Успешное создание объявления с валидными данными")
def test_create_item_success(session, auth_user, cleanup_items):
    payload = make_item_payload(auth_user["id"])
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])

    assert resp.status_code == 200
    item_id = extract_item_id(resp)
    assert item_id is not None
    cleanup_items(item_id, auth_user["headers"])

    get_resp = session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=auth_user["headers"])
    assert get_resp.status_code == 200
    assert_item_fields(get_resp.json()[0], payload, item_id)


@allure.title("TC-CR-02: Два объявления с одинаковыми полями получают разные UUID")
def test_create_duplicate_items_get_unique_ids(session, auth_user, cleanup_items):
    payload = make_item_payload(auth_user["id"])
    r1 = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])
    r2 = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])

    id1, id2 = extract_item_id(r1), extract_item_id(r2)
    cleanup_items(id1, auth_user["headers"])
    cleanup_items(id2, auth_user["headers"])

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert id1 != id2


@allure.title("TC-CR-03: Создание объявления с нулевой статистикой (BUG-04)")
def test_create_item_with_zero_statistics(session, auth_user, cleanup_items):
    payload = make_item_payload(
        auth_user["id"],
        statistics={"likes": 0, "viewCount": 0, "contacts": 0},
    )
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])
    cleanup_items(extract_item_id(resp), auth_user["headers"])

    assert resp.status_code == 200, (
        f"BUG-04: объявление с нулевой статистикой не создаётся: {resp.status_code} {resp.text}"
    )


@allure.title("TC-CR-03b: Создание объявления с нулевой ценой (BUG-04)")
def test_create_item_with_zero_price(session, auth_user, cleanup_items):
    payload = make_item_payload(auth_user["id"], price=0)
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])
    cleanup_items(extract_item_id(resp), auth_user["headers"])

    assert resp.status_code == 200, (
        f"BUG-04: объявление с price=0 не создаётся: {resp.status_code} {resp.text}"
    )


@allure.title("TC-CR-04: Невалидные данные при создании объявления возвращают 400 ({case})")
@pytest.mark.parametrize(
    ("case", "overrides", "bug_id"),
    [
        ("пустое имя", {"name": ""}, None),
        ("имя из пробелов", {"name": "     "}, "BUG-08"),
        ("имя 5000 символов", {"name": "Ж" * 5000}, "BUG-12"),
        ("цена строкой", {"price": "9900"}, None),
        ("цена bool", {"price": True}, None),
        ("отрицательная цена", {"price": -1}, "BUG-02"),
        ("отрицательные likes", {"statistics": {"likes": -1, "viewCount": 1, "contacts": 1}}, "BUG-03"),
        ("отрицательный viewCount", {"statistics": {"likes": 1, "viewCount": -1, "contacts": 1}}, "BUG-03"),
        ("отрицательные contacts", {"statistics": {"likes": 1, "viewCount": 1, "contacts": -1}}, "BUG-03"),
    ],
)
def test_create_item_invalid_payload(session, auth_user, cleanup_items, case, overrides, bug_id):
    payload = make_item_payload(auth_user["id"], **overrides)
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])
    cleanup_items(extract_item_id(resp), auth_user["headers"])

    prefix = f"{bug_id} ({case})" if bug_id else case
    assert resp.status_code == 400, f"{prefix}: ожидали 400, получили {resp.status_code} ({resp.text})"


@allure.title("TC-CR-04b: Переполнение price возвращает 400 с корректным сообщением (BUG-09)")
def test_create_item_price_overflow_error_message(session, auth_user):
    payload = make_item_payload(auth_user["id"], price=99_999_999_999_999_999_999_999_999_999)
    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=auth_user["headers"])

    assert resp.status_code == 400
    body = resp.json()
    assert body.get("result", {}).get("message"), (
        f"BUG-09: пустой result.message и некорректный status при переполнении price: {body}"
    )


@allure.title("TC-CR-05: Нельзя создать объявление с чужим sellerID или подменой X-UserId")
def test_create_item_foreign_seller_id(session, auth_user, register_user, cleanup_items):
    other_user = register_user()
    payload = make_item_payload(other_user["id"])
    headers = {**auth_user["headers"], "X-UserId": str(other_user["id"])}

    resp = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=headers)
    cleanup_items(extract_item_id(resp), other_user["headers"])

    assert resp.status_code in (400, 403)


@allure.title("TC-GET-01: Получение существующего объявления по UUID")
def test_get_item_by_id(session, created_item):
    resp = session.get(
        f"{BASE_URL}/api/1/item/{created_item['id']}",
        headers=created_item["user"]["headers"],
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert_item_fields(items[0], created_item["payload"], created_item["id"])


@allure.title("TC-GET-02: Запрос несуществующего UUID возвращает 404")
def test_get_item_not_found(session, auth_user):
    resp = session.get(f"{BASE_URL}/api/1/item/{uuid.uuid4()}", headers=auth_user["headers"])
    assert resp.status_code == 404


@allure.title("TC-GET-03: Запрос объявления по невалидному id возвращает 400")
def test_get_item_invalid_id(session, auth_user):
    resp = session.get(f"{BASE_URL}/api/1/item/not-a-uuid", headers=auth_user["headers"])
    assert resp.status_code == 400


@allure.title("TC-SEL-01: Получение всех объявлений продавца")
def test_get_seller_items(session, created_item):
    user = created_item["user"]
    resp = session.get(f"{BASE_URL}/api/1/{user['id']}/item", headers=user["headers"])

    assert resp.status_code == 200
    items = resp.json()
    ids = [item["id"] for item in items]
    assert created_item["id"] in ids
    assert all(item["sellerId"] == user["id"] for item in items)


@allure.title("TC-SEL-02: Невалидный sellerID в запросе списка объявлений возвращает 400 ({bad_id})")
@pytest.mark.parametrize("bad_id", ["abc", "-1", "0"])
def test_get_seller_items_invalid_id(session, auth_user, bad_id):
    resp = session.get(f"{BASE_URL}/api/1/{bad_id}/item", headers=auth_user["headers"])
    assert resp.status_code == 400, (
        f"BUG-07 (sellerID={bad_id}): ожидали 400, получили {resp.status_code} ({resp.text})"
    )


@allure.title("TC-ST-01: Статистика v{version} совпадает с переданной при создании")
@pytest.mark.parametrize("version", [1, 2])
def test_get_statistic_success(session, created_item, version):
    resp = session.get(
        f"{BASE_URL}/api/{version}/statistic/{created_item['id']}",
        headers=created_item["user"]["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0] == created_item["payload"]["statistics"]


@allure.title("TC-ST-02: Статистика v{version} по несуществующему UUID возвращает 404")
@pytest.mark.parametrize("version", [1, 2])
def test_get_statistic_not_found(session, auth_user, version):
    resp = session.get(f"{BASE_URL}/api/{version}/statistic/{uuid.uuid4()}", headers=auth_user["headers"])
    assert resp.status_code == 404


@allure.title("TC-ST-03: Статистика v{version} по невалидному id возвращает 400 (BUG-06)")
@pytest.mark.parametrize("version", [1, 2])
def test_get_statistic_invalid_id(session, auth_user, version):
    resp = session.get(f"{BASE_URL}/api/{version}/statistic/not-a-uuid", headers=auth_user["headers"])
    assert resp.status_code == 400, (
        f"BUG-06 (v{version}): ожидали HTTP 400, получили {resp.status_code} ({resp.text})"
    )


@allure.title("TC-ST-04: Статистика v{version} удалённого объявления возвращает 404 (BUG-05)")
@pytest.mark.parametrize("version", [1, 2])
def test_get_statistic_after_delete(session, created_item, version):
    headers = created_item["user"]["headers"]
    item_id = created_item["id"]

    del_resp = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)
    assert del_resp.status_code == 200

    stat_resp = session.get(f"{BASE_URL}/api/{version}/statistic/{item_id}", headers=headers)
    assert stat_resp.status_code == 404, (
        f"BUG-05 (v{version}): статистика после удаления вернула {stat_resp.status_code} ({stat_resp.text})"
    )


@allure.title("TC-DEL-01: Владелец успешно удаляет своё объявление")
def test_delete_own_item(session, created_item):
    headers = created_item["user"]["headers"]
    item_id = created_item["id"]

    del_resp = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)
    assert del_resp.status_code == 200

    get_resp = session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=headers)
    assert get_resp.status_code == 404


@allure.title("TC-DEL-02: Повторное удаление того же объявления возвращает 404")
def test_delete_item_twice(session, created_item):
    headers = created_item["user"]["headers"]
    item_id = created_item["id"]

    first = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)
    assert first.status_code == 200

    second = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)
    assert second.status_code == 404


@allure.title("TC-DEL-03: Чужой пользователь не может удалить объявление (BUG-01)")
def test_delete_foreign_item(session, created_item, register_user):
    other_user = register_user()
    item_id = created_item["id"]

    del_resp = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=other_user["headers"])
    owner_check = session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=created_item["user"]["headers"])

    assert del_resp.status_code in (403, 404), (
        f"BUG-01: чужой пользователь удалил объявление (HTTP {del_resp.status_code}, "
        f"GET у владельца после удаления → {owner_check.status_code})"
    )


@allure.title("TC-DEL-04: Удаление несуществующего UUID возвращает 404 с корректным status в теле (BUG-11)")
def test_delete_not_found_response_contract(session, auth_user):
    resp = session.delete(
        f"{BASE_URL}/api/2/item/00000000-0000-0000-0000-000000000000",
        headers=auth_user["headers"],
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("status") == "404", (
        f"BUG-11: при HTTP 404 в теле ответа указан status={body.get('status')!r}: {body}"
    )


@allure.title(
    "TC-E2E-01: Сквозной сценарий: регистрация → авторизация → создание → чтение и статистика → удаление"
)
def test_e2e_full_lifecycle(session, cleanup_items):
    username, password = random_credentials()

    with allure.step("1. Регистрация нового пользователя"):
        reg = session.post(f"{BASE_URL}/api/1/register", json={"username": username, "password": password})
        assert reg.status_code == 201
        seller_id = reg.json()["id"]

    with allure.step("2. Авторизация и получение Bearer-токена"):
        auth = session.post(f"{BASE_URL}/api/1/autorize", json={"username": username, "password": password})
        assert auth.status_code == 200
        headers = {"Authorization": f"Bearer {auth.json()['accessToken']}"}

    with allure.step("3. Создание объявления"):
        payload = make_item_payload(seller_id)
        create = session.post(f"{BASE_URL}/api/1/item", json=payload, headers=headers)
        assert create.status_code == 200
        item_id = extract_item_id(create)
        assert item_id is not None
        cleanup_items(item_id, headers)

    with allure.step("4. Получение объявления и статистики v1/v2"):
        item_resp = session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=headers)
        assert item_resp.status_code == 200
        assert_item_fields(item_resp.json()[0], payload, item_id)

        for ver in (1, 2):
            stat_resp = session.get(f"{BASE_URL}/api/{ver}/statistic/{item_id}", headers=headers)
            assert stat_resp.status_code == 200
            assert stat_resp.json()[0] == payload["statistics"]

    with allure.step("5. Удаление объявления и проверка 404"):
        del_resp = session.delete(f"{BASE_URL}/api/2/item/{item_id}", headers=headers)
        assert del_resp.status_code == 200
        assert session.get(f"{BASE_URL}/api/1/item/{item_id}", headers=headers).status_code == 404
