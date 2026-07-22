"""Life OS — генерация стилизованных HTML-страниц для vault."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from src.logging_setup import get_logger
from src.processing.note_writer import parse_frontmatter

log = get_logger("vault_pages")

SKIP_INDEX_ROOT = True

FOLDER_LABELS = {
    "Inbox": "Inbox",
    "Notes": "Notes",
    "Projects": "Projects",
    "Tags": "Tags",
    "Areas": "Areas",
    "Prompt-Engineering": "Prompt Engineering",
    "Vibe-Coding": "Vibe Coding",
    "Longevity": "Longevity",
    "Immortality": "Immortality",
}

FOLDER_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
    '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>'
)


def _label(name: str) -> str:
    return FOLDER_LABELS.get(name, name.replace("-", " "))


def _rel_to_root(folder: Path, vault: Path) -> str:
    depth = len(folder.relative_to(vault).parts)
    return "/".join([".."] * depth) if depth else "."


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    return f"{size / 1024:.1f} kB"


def _fmt_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%m.%Y, %H:%M:%S")


def _shared_css() -> str:
    return """
    :root {
      --bg-primary: #fafafa; --bg-secondary: #f0f2f5;
      --accent-blue: #1a5cff; --accent-azure: #4a8aff; --accent-cobalt: #0033cc;
      --accent-red: #dc3545; --text-ink: #1a1f36; --text-muted: #5a6278;
      --white: #ffffff; --glow-blue: rgba(26, 92, 255, 0.15);
      --glow-red: rgba(220, 53, 69, 0.25); --border-blue: rgba(26, 92, 255, 0.2);
      --font-main: 'Inter', system-ui, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
      --font-display: 'Playfair Display', Georgia, serif;
      --nav-height: 64px; --transition: 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-main); background: var(--bg-primary);
      color: var(--text-ink); line-height: 1.65; min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }
    a { color: inherit; text-decoration: none; }
    .nav {
      position: sticky; top: 0; z-index: 100; height: var(--nav-height);
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 clamp(1rem, 4vw, 2.5rem);
      background: rgba(250, 250, 250, 0.92);
      backdrop-filter: blur(16px); border-bottom: 1px solid var(--border-blue);
    }
    .nav__logo { display: flex; align-items: center; gap: 0.6rem; font-weight: 600; }
    .nav__seal {
      width: 34px; height: 34px; border-radius: 50%; background: var(--accent-red);
      display: flex; align-items: center; justify-content: center;
      color: var(--white); font-family: var(--font-display); font-weight: 700;
      box-shadow: 0 0 12px var(--glow-red);
    }
    .nav__back {
      font-size: 0.85rem; font-weight: 500; color: var(--accent-blue);
      transition: color var(--transition);
    }
    .nav__back:hover { color: var(--accent-cobalt); }
    .page {
      max-width: 960px; margin: 0 auto;
      padding: 2.5rem clamp(1rem, 4vw, 2rem) 4rem;
    }
    .breadcrumbs {
      font-family: var(--font-mono); font-size: 0.75rem;
      color: var(--text-muted); margin-bottom: 1.5rem;
      display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
    }
    .breadcrumbs a { color: var(--accent-blue); }
    .breadcrumbs a:hover { color: var(--accent-cobalt); }
    .breadcrumbs .sep { opacity: 0.4; }
    .page-header { margin-bottom: 2.5rem; }
    .page-label {
      font-family: var(--font-mono); font-size: 0.72rem;
      text-transform: uppercase; letter-spacing: 0.14em;
      color: var(--accent-blue); margin-bottom: 0.5rem;
    }
    .page-title {
      font-family: var(--font-display); font-size: clamp(1.6rem, 4vw, 2.2rem);
      font-weight: 700; text-shadow: 0 1px 12px rgba(26, 92, 255, 0.1);
    }
    .page-desc { color: var(--text-muted); margin-top: 0.5rem; font-size: 0.95rem; }
    .section-title {
      font-family: var(--font-display); font-size: 1.1rem;
      margin-bottom: 1rem; color: var(--text-ink);
    }
    .folders {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 0.75rem; margin-bottom: 2.5rem;
    }
    .folder-card {
      display: flex; align-items: center; gap: 0.65rem;
      padding: 1rem 1.1rem; background: var(--white);
      border: 1px solid var(--border-blue); border-radius: 10px;
      font-weight: 500; font-size: 0.9rem;
      transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
    }
    .folder-card:hover {
      transform: translateY(-3px); border-color: var(--accent-blue);
      box-shadow: 0 0 20px var(--glow-blue);
    }
    .folder-card .icon {
      width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0;
      background: linear-gradient(135deg, rgba(26,92,255,0.08), rgba(74,138,255,0.15));
      display: flex; align-items: center; justify-content: center; color: var(--accent-blue);
    }
    .folder-card .icon svg { width: 18px; height: 18px; }
    .file-list { list-style: none; }
    .file-item {
      display: grid; grid-template-columns: 1fr auto auto;
      gap: 1rem; align-items: center;
      padding: 1rem 1.25rem; background: var(--white);
      border: 1px solid var(--border-blue); border-radius: 10px;
      margin-bottom: 0.65rem;
      transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
    }
    .file-item:hover {
      transform: translateX(4px); border-color: var(--accent-blue);
      box-shadow: 0 0 20px var(--glow-blue);
    }
    .file-item__name {
      display: flex; align-items: center; gap: 0.75rem;
      font-weight: 500; font-size: 0.92rem;
    }
    .file-item__dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--accent-red); flex-shrink: 0;
      box-shadow: 0 0 8px var(--glow-red);
    }
    .file-item__meta {
      font-family: var(--font-mono); font-size: 0.72rem;
      color: var(--text-muted); white-space: nowrap;
    }
    .empty {
      text-align: center; padding: 3rem 1.5rem; color: var(--text-muted);
      background: var(--bg-secondary); border-radius: 12px;
      border: 1px dashed var(--border-blue);
    }
    .empty__icon { font-size: 2rem; margin-bottom: 0.75rem; opacity: 0.5; }
    .footer {
      text-align: center; padding: 2rem; font-size: 0.78rem;
      color: var(--text-muted); border-top: 1px solid rgba(26, 92, 255, 0.08);
    }
    .note-hero {
      background: linear-gradient(165deg, var(--white), #f5f8ff, #e8f0ff);
      border: 1px solid var(--border-blue); border-radius: 14px;
      padding: 2rem 2rem 1.5rem; margin-bottom: 2rem; position: relative;
    }
    .note-hero::after {
      content: ''; position: absolute; bottom: 0; left: 2rem; right: 2rem;
      height: 2px; background: linear-gradient(90deg, var(--accent-red), transparent);
      opacity: 0.6;
    }
    .note-title {
      font-family: var(--font-display); font-size: clamp(1.5rem, 3.5vw, 2rem);
      font-weight: 700; margin-bottom: 1rem;
    }
    .note-meta { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .note-badge {
      font-family: var(--font-mono); font-size: 0.68rem;
      padding: 0.3rem 0.65rem; border-radius: 5px;
      background: rgba(26, 92, 255, 0.07); color: var(--accent-cobalt);
    }
    .note-badge--red { background: rgba(220, 53, 69, 0.08); color: var(--accent-red); }
    .note-body {
      background: var(--white); border: 1px solid var(--border-blue);
      border-radius: 14px; padding: 2rem;
    }
    .note-section {
      font-family: var(--font-display); font-size: 1.2rem; font-weight: 700;
      color: var(--accent-cobalt); margin: 1.75rem 0 0.75rem;
      padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-blue);
    }
    .note-section:first-child { margin-top: 0; }
    .note-body p { color: var(--text-muted); margin-bottom: 0.75rem; }
    .note-list { margin: 0.5rem 0 1rem 1.25rem; color: var(--text-muted); }
    .note-list li { margin-bottom: 0.4rem; }
    .note-list li::marker { color: var(--accent-blue); }
    .note-thoughts {
      min-height: 48px; padding: 1rem; margin-top: 0.5rem;
      background: var(--bg-secondary); border-radius: 8px;
      border: 1px dashed var(--border-blue); color: var(--text-muted);
      font-style: italic; font-size: 0.9rem;
    }
    .reveal { opacity: 0; transform: translateY(20px); animation: fadeUp 0.6s ease forwards; }
    .reveal:nth-child(2) { animation-delay: 0.08s; }
    .reveal:nth-child(3) { animation-delay: 0.16s; }
    @keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }
    @media (max-width: 640px) {
      .file-item { grid-template-columns: 1fr; gap: 0.35rem; }
    }
    """


def _page_shell(title: str, root_rel: str, back_href: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} — Life OS</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Playfair+Display:wght@500;700&display=swap" rel="stylesheet">
  <style>{_shared_css()}</style>
</head>
<body>
  <nav class="nav">
    <a href="{html.escape(root_rel)}/index.html" class="nav__logo">
      <span class="nav__seal">L</span> Life OS
    </a>
    <a href="{html.escape(back_href)}" class="nav__back">← Назад</a>
  </nav>
  {body}
  <footer class="footer">Life OS · Кристаллический свиток знаний</footer>
</body>
</html>"""


def _breadcrumbs(folder: Path, vault: Path) -> str:
    parts = folder.relative_to(vault).parts
    crumbs = [f'<a href="{_rel_to_root(folder, vault)}/index.html">Life OS</a>']
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            up = len(parts) - i - 1
            link = ("../" * up) + "index.html"
            crumbs.append(f'<span class="sep">/</span><a href="{link}">{html.escape(_label(part))}</a>')
        else:
            crumbs.append(f'<span class="sep">/</span><span>{html.escape(_label(part))}</span>')
    return '<nav class="breadcrumbs">' + "".join(crumbs) + "</nav>"


def _render_folder_index(folder: Path, vault: Path) -> str:
    rel_root = _rel_to_root(folder, vault)
    parent = "../index.html"

    subdirs = sorted(d for d in folder.iterdir() if d.is_dir() and not d.name.startswith("."))
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".md")

    folders_html = ""
    if subdirs:
        cards = [
            f'<a href="{html.escape(d.name)}/index.html" class="folder-card reveal">'
            f'<span class="icon">{FOLDER_SVG}</span><span>{html.escape(_label(d.name))}</span></a>'
            for d in subdirs
        ]
        folders_html = '<h2 class="section-title reveal">Папки</h2><div class="folders">' + "".join(cards) + "</div>"

    files_html = ""
    if files:
        items = [
            f'<li class="reveal"><a href="{html.escape(f.stem)}.html" class="file-item">'
            f'<span class="file-item__name"><span class="file-item__dot"></span>{html.escape(f.stem)}</span>'
            f'<span class="file-item__meta">{_fmt_size(f.stat().st_size)}</span>'
            f'<span class="file-item__meta">{_fmt_mtime(f)}</span></a></li>'
            for f in files
        ]
        files_html = '<h2 class="section-title reveal">Заметки</h2><ul class="file-list">' + "".join(items) + "</ul>"

    empty_html = ""
    if not subdirs and not files:
        empty_html = (
            '<div class="empty reveal"><div class="empty__icon">◇</div>'
            "<p>Папка пуста. Новые заметки появятся после захвата материалов.</p></div>"
        )

    rel_parts = folder.relative_to(vault).parts
    title = " / ".join(_label(p) for p in rel_parts)

    body = f"""
  <main class="page">
    {_breadcrumbs(folder, vault)}
    <header class="page-header reveal">
      <p class="page-label">// {" / ".join(rel_parts)}</p>
      <h1 class="page-title">{html.escape(title)}</h1>
      <p class="page-desc">{len(subdirs)} папок · {len(files)} заметок</p>
    </header>
    {folders_html}
    {files_html}
    {empty_html}
  </main>"""

    return _page_shell(title, rel_root, parent, body)


def _md_body_to_html(text: str) -> str:
    parts: list[str] = []
    in_list = False
    in_thoughts = False

    for line in text.splitlines():
        if line.startswith("## "):
            if in_thoughts:
                parts.append("</div>")
                in_thoughts = False
            if in_list:
                parts.append("</ul>")
                in_list = False
            heading = line[3:].strip()
            parts.append(f'<h2 class="note-section">{html.escape(heading)}</h2>')
            if heading == "Мои мысли":
                in_thoughts = True
                parts.append('<div class="note-thoughts">')
            continue

        if in_thoughts:
            if line.strip():
                parts.append(html.escape(line) + "<br>")
            continue

        if line.startswith("- "):
            if not in_list:
                parts.append('<ul class="note-list">')
                in_list = True
            parts.append(f"<li>{html.escape(line[2:])}</li>")
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False

        if line.strip():
            parts.append(f"<p>{html.escape(line)}</p>")

    if in_list:
        parts.append("</ul>")
    if in_thoughts:
        parts.append("</div>")

    return "\n".join(parts)


def _load_note(md_path: Path) -> tuple[dict, str]:
    text = md_path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].lstrip("\n")
    return meta, body


def _render_note_page(md_path: Path, vault: Path) -> str:
    meta, content = _load_note(md_path)
    folder = md_path.parent
    rel_root = _rel_to_root(folder, vault)

    badges = []
    for key in ("date", "area", "type", "status"):
        val = meta.get(key)
        if val:
            cls = "note-badge--red" if key == "status" else "note-badge"
            badges.append(f'<span class="{cls}">{html.escape(str(key))}: {html.escape(str(val))}</span>')

    source = meta.get("source")
    if source:
        badges.append(f'<span class="note-badge">source: {html.escape(str(source))}</span>')

    title = str(meta.get("title", md_path.stem))
    body_html = _md_body_to_html(content)

    page_body = f"""
  <main class="page">
    {_breadcrumbs(folder, vault)}
    <article>
      <header class="note-hero reveal">
        <h1 class="note-title">{html.escape(title)}</h1>
        <div class="note-meta">{"".join(badges)}</div>
      </header>
      <div class="note-body reveal">{body_html}</div>
    </article>
  </main>"""

    return _page_shell(title, rel_root, "index.html", page_body)


def generate_vault_pages(vault: Path) -> int:
    """Генерирует index.html в подпапках и .html для каждой .md-заметки."""
    if not vault.is_dir():
        log.warning("Vault не найден: %s", vault)
        return 0

    count = 0
    for folder in sorted(vault.rglob("*")):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if SKIP_INDEX_ROOT and folder == vault:
            continue
        (folder / "index.html").write_text(_render_folder_index(folder, vault), encoding="utf-8")
        count += 1

    for md in sorted(vault.rglob("*.md")):
        md.with_suffix(".html").write_text(_render_note_page(md, vault), encoding="utf-8")
        count += 1

    log.info("Сгенерировано HTML-страниц: %d в %s", count, vault)
    return count
