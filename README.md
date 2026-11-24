# Тестовое задание QA-стажёра (осень 2026)

Репозиторий содержит решения обеих частей тестового задания:

- **Задание 1** — найденные и приоритизированные баги по скриншотам: [TASK1.md](TASK1.md)
- **Задание 2.1 (API):**
  - Тест-кейсы: [TESTCASES.md](TESTCASES.md)
  - Автотесты на `pytest` + `requests`: [conftest.py](conftest.py) и [test_api.py](test_api.py)
  - Найденные дефекты API: [BUGS.md](BUGS.md)
  - Использованные промпты к ИИ: [PROMPTS.md](PROMPTS.md)

## Установка и запуск автотестов

Требуется Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Все тесты независимы: в фикстурах (`conftest.py`) перед тестом динамически регистрируется новый пользователь, получается Bearer-токен через `/api/1/autorize`, а все созданные объявления удаляются после завершения теста через `DELETE /api/2/item/{id}`.

> **Примечание о падающих тестах:** тесты, которые обнаруживают дефекты стенда, падают с указанием номера бага (`BUG-01..BUG-12`), подробно описанного в [BUGS.md](BUGS.md).

## Отчёты о прогоне (HTML и Allure)

Пример сформированного HTML-отчёта приложен в корне репозитория: [report.html](report.html).

Сформировать свежий самодостаточный HTML-отчёт (`pytest-html`):

```bash
pytest --html=report.html --self-contained-html
```

Также подключён `allure-pytest` — результаты прогона автоматически сохраняются в `allure-results/`. Для просмотра Allure-отчёта (при установленном Allure CLI):

```bash
allure serve allure-results
```

## Линтер и форматтер

Правила `ruff` зафиксированы в `pyproject.toml`:

```bash
ruff check .
ruff format .
```
