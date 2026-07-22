# Life OS

Персональная система управления знаниями: автоматический конвейер сбора знаний в Obsidian.

**Конвейер:** URL / PDF / текст / YouTube → извлечение контента → Claude API
(классификация + саммари + научный блок + теги) → структурированная `.md`-заметка
в хранилище Obsidian → запись в SQLite → RAG-индекс со связями `related`.

**Области:** промпт-инжиниринг · вайб-кодинг · долголетие · бессмертие.

## Стек

Obsidian · Python 3.12 · SQLite · локальный RAG (TF-IDF) · Claude API · Git. ОС: Windows.

## Установка и запуск

```text
pip install -r requirements.txt
copy .env.example .env             # вписать ANTHROPIC_API_KEY
python init_db.py                  # создать БД (конфиг читается, схема применяется)

python capture.py https://arxiv.org/abs/2401.01234      # одна статья/PDF/видео/текст
python capture.py C:\Downloads\paper.pdf
python capture.py sources.txt --batch                   # пакет: по источнику на строку
```

Путь к хранилищу Obsidian задаётся в `config.yaml` (`vault_path`) либо запрашивается
один раз при первом запуске `capture.py` и сохраняется в конфиг.

## Тестирование

```text
python -m pytest tests/            # 38 тестов: юнит + интеграция end-to-end
```

Интеграционные тесты прогоняют весь конвейер на моке Claude API — сеть и ключ не нужны.
Покрыто: парсинг ответа модели, извлечение из HTML, arXiv/bioRxiv-ссылки, YouTube ID,
чанкинг и косинусный поиск RAG, пороги классификации, разделение тегов,
авто-раскладка по /Areas, дедупликация, обработка ошибок API без падения конвейера,
научный блок только для `type: paper`.

## Логирование

Два независимых канала:
1. **Файл + консоль** — `logs/lifeos.log` (ротация 1 МБ × 3), формат
   `время | уровень | модуль | сообщение`, кодировка utf-8.
2. **SQLite** — таблица `pipeline_log` фиксирует ошибки этапов
   (`extract | classify | write | index`), при этом материал помечается
   `status = failed` с причиной. Ошибка одного материала не прерывает пакет.

## Структура проекта

```text
life-os/
├── CLAUDE.md              # правила проекта (читать в начале каждого сеанса)
├── README.md
├── config.yaml            # vault_path, модель, пороги, RAG, пути
├── schema.sql             # схема SQLite
├── requirements.txt
├── pytest.ini
├── .env.example / .gitignore
├── init_db.py             # инициализация БД
├── capture.py             # CLI: python capture.py <url|файл> [--batch]
├── src/
│   ├── config.py          # загрузка config.yaml
│   ├── logging_setup.py   # логирование (файл + консоль)
│   ├── db.py              # SQLite: схема, дедуп по SHA-256, лог ошибок
│   ├── claude_client.py   # Claude API: классификация+саммари, парсинг JSON
│   ├── pipeline.py        # оркестратор конвейера
│   ├── vault.py           # структура Obsidian, теги, выбор папки
│   ├── extractors/        # url · pdf(arxiv/biorxiv) · text · youtube
│   ├── processing/        # classifier (пороги) · note_writer (строгий формат)
│   └── rag/index.py       # TF-IDF индекс, чанкинг, косинусный поиск, related
├── tests/
│   ├── test_phase0.py     # каркас, пороги, frontmatter
│   ├── test_units.py      # юнит-тесты модулей
│   └── test_pipeline.py   # интеграция end-to-end на моке Claude
├── data/                  # lifeos.sqlite3, RAG-индекс (в .gitignore)
└── logs/
```

## Формат заметки (строгий)

Frontmatter: `title, date, source, area, type, tags, related, status`.
Разделы: `## Саммари`, `## Ключевые идеи`, `## Для научных материалов`
(только при `type: paper`), `## Мои мысли` (всегда пустой — ручное заполнение),
`## Исходник`.

## Правила (кратко)

- Существующие заметки никогда не перезаписываются (при коллизии имени — числовой суффикс).
- Теги в заметку берутся только из уже существующих в хранилище; новые складываются
  в БД как `approved = 0` и предлагаются владельцу, а не создаются автоматически.
- `area = other` + `#needs-review` при уверенности ниже порога; заметка остаётся в /Inbox.
- Авто-раскладка в /Areas/<область> — при уверенности ≥ `thresholds.auto_area`.
- API-ключ только из `.env`. Windows-совместимость: `pathlib`, явный `utf-8`.

## Известные ограничения / направления развития

- RAG использует литеральное совпадение токенов (TF-IDF) без лемматизации —
  разные словоформы («старение»/«старения») не сопоставляются. Замена слоя
  на sentence-transformers снимет ограничение без изменения интерфейса `RagIndex`.
- YouTube-транскрипты зависят от доступности субтитров у видео.
