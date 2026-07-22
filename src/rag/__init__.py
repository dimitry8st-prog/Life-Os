"""Life OS — локальный RAG (фаза 3).

Планируется:
- chunker.py    — чанкинг (размер/перекрытие из config.yaml)
- embedder.py   — локальные эмбеддинги
- index.py      — индекс + поиск top-k по косинусной близости
- linker.py     — автозаполнение related (порог related_similarity)
- dedup.py      — дедупликация по content_hash
"""
