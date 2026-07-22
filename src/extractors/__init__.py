"""Life OS — извлечение основного контента (без навигации, рекламы, комментариев).

Реализация по фазам:
- url_extractor    — фаза 1
- pdf_extractor    — фаза 2 (локальные PDF + arXiv/bioRxiv)
- text_extractor   — фаза 1
- youtube_extractor — фаза 4 (транскрипты)
"""
