-- Life OS — схема базы данных (SQLite)

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Захваченные материалы
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,                 -- URL или имя файла
    source_type   TEXT NOT NULL DEFAULT 'url'    -- url | pdf | text | youtube
                  CHECK (source_type IN ('url','pdf','text','youtube')),
    title         TEXT,
    area          TEXT NOT NULL DEFAULT 'other'
                  CHECK (area IN ('prompt-engineering','vibe-coding',
                                  'longevity','immortality','other')),
    area_confidence REAL,                        -- 0..1, уверенность классификации
    note_type     TEXT                           -- article | paper | video | book | note
                  CHECK (note_type IN ('article','paper','video','book','note')),
    note_path     TEXT,                          -- путь к .md в vault
    content_hash  TEXT UNIQUE,                   -- SHA-256 контента (дедупликация)
    status        TEXT NOT NULL DEFAULT 'inbox'  -- inbox | processed | filed | failed
                  CHECK (status IN ('inbox','processed','filed','failed')),
    error         TEXT,                          -- причина при status = failed
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_area   ON items(area);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_hash   ON items(content_hash);

-- Теги (только существующие в хранилище; новые — через approved)
CREATE TABLE IF NOT EXISTS tags (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    approved INTEGER NOT NULL DEFAULT 1          -- 0 = предложен, ждёт одобрения
);

CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (item_id, tag_id)
);

-- Связи между заметками (заполняется RAG на фазе 3)
CREATE TABLE IF NOT EXISTS relations (
    item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    related_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    similarity  REAL,
    PRIMARY KEY (item_id, related_id)
);

-- Журнал ошибок конвейера (ошибки не прерывают процесс)
CREATE TABLE IF NOT EXISTS pipeline_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    INTEGER REFERENCES items(id) ON DELETE SET NULL,
    stage      TEXT NOT NULL,                    -- extract | classify | summarize | write | index
    level      TEXT NOT NULL DEFAULT 'ERROR',
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
