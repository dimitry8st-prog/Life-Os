"""Life OS — интерактивная библиотека материалов на Streamlit."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from src.config import load_config
from src.dashboard_data import AREA_LABELS, list_items, note_preview, set_state
from src.db import init_db


st.set_page_config(page_title="Life OS", page_icon="🧠", layout="wide")
st.title("Life OS · Библиотека знаний")
st.caption("Новые материалы, поиск, избранное и прогресс чтения в одном месте")

cfg = load_config()
init_db(cfg.db_path)
conn = sqlite3.connect(cfg.db_path)
conn.row_factory = sqlite3.Row

with st.sidebar:
    st.header("Фильтры")
    search = st.text_input("Поиск", placeholder="Название или источник")
    area_options = ["Все", *AREA_LABELS]
    area = st.selectbox("Тема", area_options, format_func=lambda x: AREA_LABELS.get(x, x))
    state = st.radio("Состояние", ["Все", "Непрочитанные", "Прочитанные", "Избранное"])
    note_type = st.selectbox("Тип", ["Все", "article", "paper", "video", "book", "note"])
    st.divider()
    if st.button("Обновить список", use_container_width=True):
        st.rerun()

all_items = list_items(conn)
read_count = sum(row["is_read"] for row in all_items)
favorite_count = sum(row["is_favorite"] for row in all_items)
new_count = len(all_items) - read_count
m1, m2, m3, m4 = st.columns(4)
m1.metric("Всего", len(all_items))
m2.metric("Новых", new_count)
m3.metric("Прочитано", read_count)
m4.metric("Избранное", favorite_count)

tab_library, tab_week = st.tabs(["Библиотека", "Лучшее за неделю"])
with tab_library:
    items = list_items(conn, search, area, state, note_type)
    st.subheader(f"Материалы · {len(items)}")
    if not items:
        st.info("По выбранным фильтрам материалов нет.")
    for row in items:
        title = row["title"] or "Без названия"
        with st.container(border=True):
            heading, badges = st.columns([4, 1])
            heading.markdown(f"### {title}")
            badges.caption(AREA_LABELS.get(row["area"], row["area"]))
            st.write(note_preview(row["note_path"]))
            st.caption(f"{row['note_type'] or 'материал'} · добавлено {row['created_at']} · релевантность {float(row['area_confidence'] or 0):.0%}")
            c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
            if c1.button("✓ Прочитано" if not row["is_read"] else "↩ Не прочитано", key=f"read-{row['id']}"):
                set_state(conn, row["id"], "is_read", not row["is_read"])
                st.rerun()
            if c2.button("★ В избранное" if not row["is_favorite"] else "☆ Убрать", key=f"fav-{row['id']}"):
                set_state(conn, row["id"], "is_favorite", not row["is_favorite"])
                st.rerun()
            if row["source"].startswith(("http://", "https://")):
                c3.link_button("Оригинал ↗", row["source"])
            if row["note_path"] and Path(row["note_path"]).exists():
                c4.caption(f"Заметка: {row['note_path']}")

with tab_week:
    weekly = conn.execute("""
        SELECT i.*, COALESCE(r.is_read, 0) is_read, COALESCE(r.is_favorite, 0) is_favorite
        FROM items i LEFT JOIN reading_state r ON r.item_id=i.id
        WHERE i.status != 'failed' AND datetime(i.created_at) >= datetime('now', '-7 days')
        ORDER BY COALESCE(i.area_confidence, 0) DESC, datetime(i.created_at) DESC LIMIT 10
    """).fetchall()
    st.subheader("10 наиболее релевантных материалов за последние 7 дней")
    for number, row in enumerate(weekly, 1):
        st.markdown(f"**{number}. {row['title'] or 'Без названия'}** · {AREA_LABELS.get(row['area'], row['area'])}")
        st.write(note_preview(row["note_path"], 240))

conn.close()
