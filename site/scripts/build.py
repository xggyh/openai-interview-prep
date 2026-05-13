#!/usr/bin/env python3
"""Build static HTML site from scraped data + analysis markdown."""

import json, re, html, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent
SITE = ROOT / "site"
RAW_DIR = SITE / "data" / "raw"
ANALYSES_DIR = SITE / "analyses"
PUBLIC_DIR = ROOT / "public"  # final output goes here for GH Pages
QUESTIONS_JSON = ROOT / "openai-interview-questions.json"

# We rely on a minimal markdown subset and CDN-loaded prism.js for syntax highlighting.
# Markdown features supported by our parser:
#   - # / ## / ### headings
#   - **bold**, *italic*, `inline`
#   - ```lang fenced code blocks
#   - - bullet lists (single level)
#   - 1. numbered lists
#   - > blockquote
#   - paragraphs
#   - --- horizontal rules
#   - Special callouts: > [!key] ..., > [!pitfall] ..., > [!followup] ...
#   - ASCII diagrams: wrap in ```ascii fence

CALLOUT_TYPES = {"key": "key", "pitfall": "pitfall", "followup": "followup"}

def esc(s: str) -> str:
    return html.escape(s, quote=False)

def md_inline(s: str) -> str:
    """Inline markdown: bold/italic/code/links."""
    # Escape HTML first, then re-introduce markdown markers.
    s = esc(s)
    # Inline code first to avoid mangling its contents.
    code_chunks = []
    def stash_code(m):
        code_chunks.append(m.group(1))
        return f"\x00CODE{len(code_chunks)-1}\x00"
    s = re.sub(r"`([^`]+)`", stash_code, s)
    # Links: [text](url)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    # Bold **x**
    s = re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", s)
    # Italic *x*
    s = re.sub(r"(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])", r"<em>\1</em>", s)
    # Restore inline code
    for i, c in enumerate(code_chunks):
        s = s.replace(f"\x00CODE{i}\x00", f"<code>{c}</code>")
    return s

def md_to_html(md: str) -> str:
    """Block-level markdown → HTML. Supports the subset above."""
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        m = re.match(r"^```(\w*)\s*$", stripped)
        if m:
            lang = m.group(1) or "plaintext"
            i += 1
            code_lines = []
            while i < n and not re.match(r"^```\s*$", lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code = "\n".join(code_lines)
            if lang == "ascii":
                out.append(f'<div class="ascii-diagram">{esc(code)}</div>')
            else:
                out.append(f'<pre class="language-{lang}"><code class="language-{lang}">{esc(code)}</code></pre>')
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = md_inline(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^---+\s*$", stripped):
            out.append("<hr />")
            i += 1
            continue

        # Blockquote / callouts
        if stripped.startswith(">"):
            # Detect special callout: > [!type] body...
            buf = []
            kind = None
            while i < n and lines[i].lstrip().startswith(">"):
                body = re.sub(r"^\s*>\s?", "", lines[i])
                cm = re.match(r"^\[!(\w+)\]\s*(.*)$", body)
                if cm and kind is None:
                    kind = cm.group(1).lower()
                    body = cm.group(2)
                buf.append(body)
                i += 1
            inner = md_to_html("\n".join(buf))
            if kind in CALLOUT_TYPES:
                label = {"key": "核心要点", "pitfall": "易错点 / Red Flag", "followup": "延伸 / Follow-up"}[kind]
                out.append(f'<div class="callout callout-{kind}"><strong>{label}</strong>{inner}</div>')
            else:
                out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # Bullet list
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            li_html = "".join(f"<li>{md_inline(it)}</li>" for it in items)
            out.append(f"<ul>{li_html}</ul>")
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            li_html = "".join(f"<li>{md_inline(it)}</li>" for it in items)
            out.append(f"<ol>{li_html}</ol>")
            continue

        # Blank line
        if stripped == "":
            i += 1
            continue

        # Paragraph: gather until blank or block start
        para_lines = []
        while i < n and lines[i].strip() and not (
            re.match(r"^(#{1,4}\s|>|\d+\.\s|[-*]\s|```|---+\s*$)", lines[i].strip())
        ):
            para_lines.append(lines[i].strip())
            i += 1
        para = " ".join(para_lines)
        out.append(f"<p>{md_inline(para)}</p>")

    return "\n".join(out)


def tag_class(tag: str) -> str:
    """Build CSS class slug from a tag like 'System Design' or 'Mobile System Design'."""
    return "tag tag-" + re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def parse_timeline(timeline_raw: str):
    """Split timeline text into structured variant entries.
    Each entry: {date, company, level, notes (optional)}.
    Heuristic: dates match 'Early/Mid/Late <Month>, <Year>'.
    """
    if not timeline_raw:
        return []
    lines = [l.strip() for l in timeline_raw.split("\n")]
    # Skip the header part up to and including "Region" lines
    body_start = 0
    for i, l in enumerate(lines):
        if re.match(r"^(Early|Mid|Late)\s+\w+,\s+\d+$", l):
            body_start = i
            break
    entries = []
    cur = None
    i = body_start
    while i < len(lines):
        l = lines[i]
        # Skip "Show N More" / "Show Less"
        if re.match(r"^Show\s+\d+\s+More$", l) or l == "Show Less":
            i += 1
            continue
        if re.match(r"^(Early|Mid|Late)\s+\w+,\s+\d+$", l):
            if cur:
                entries.append(cur)
            cur = {"date": l, "company": None, "level": None, "notes": []}
            i += 1
            continue
        if cur is not None and cur["company"] is None and l and l != "OpenAI" and not re.match(r"^How would you|^[\d.]+ Stars?|^Empty|^\(\d+\)", l):
            cur["company"] = l
            i += 1
            continue
        if cur is not None and cur["level"] is None and l:
            cur["level"] = l
            i += 1
            continue
        if cur is not None and l:
            cur["notes"].append(l)
            i += 1
            continue
        i += 1
    if cur:
        entries.append(cur)
    # Filter: many entries are pure header noise — keep only those with date+company+level
    return [e for e in entries if e["date"] and e["company"]]


def parse_comments(comments_raw: str):
    """Parse comments section heuristically.
    Skip the boilerplate around "Comment / Anonymous / Posting as ..." and "Red Flags to Avoid" embedded.
    Return list of {body}.
    """
    if not comments_raw:
        return []
    # Drop everything from "Question Timeline" onward (we already have it)
    cut = re.split(r"^Question Timeline$", comments_raw, flags=re.M)[0]
    # Drop "Red Flags to Avoid" — those are page metadata, not user comments
    cut = re.sub(r"Red Flags to Avoid[\s\S]*", "", cut)
    lines = cut.split("\n")
    out = []
    # Look for blocks. Simplest: paragraphs separated by blank lines, skip nav-y short ones.
    para = []
    for l in lines:
        if l.strip() == "":
            if para:
                txt = " ".join(p for p in para if p)
                if len(txt) > 30 and "Anonymous" not in txt and "Posting as" not in txt and not txt.startswith(("Comment", "Comments")):
                    out.append({"body": txt})
                para = []
        else:
            para.append(l.strip())
    if para:
        txt = " ".join(p for p in para if p)
        if len(txt) > 30 and "Anonymous" not in txt and not txt.startswith(("Comment", "Comments")):
            out.append({"body": txt})
    return out


def render_index(questions, type_groups, recency_sorted):
    """Render index.html."""
    types_meta = [
        ("Coding", "Coding 题（算法 / LLD 编码）"),
        ("System Design", "System Design 题（架构设计）"),
        ("People Management", "People Management（管理向）"),
        ("Behavioral", "Behavioral（行为面试）"),
        ("Mobile System Design", "Mobile System Design（移动端设计）"),
    ]
    cards = []
    for q in recency_sorted:
        slug_id = q["slug"].rsplit("/", 1)[-1]
        href = f"questions/{slug_id}.html"
        tag = q["type"]
        level = q["level"] or "—"
        reports = q["reportedUsers"] or 0
        last = q["lastAsked"] or "—"
        desc = (q.get("description") or "").strip()
        if len(desc) > 180:
            desc = desc[:180].rsplit(" ", 1)[0] + "…"
        card = f"""
<div class="q-card" data-type="{esc(tag)}" data-level="{esc(level)}">
  <a class="q-title" href="{href}">{esc(q['title'])}</a>
  <div class="q-tags">
    <span class="{tag_class(tag)}">{esc(tag)}</span>
    <span class="tag tag-level">{esc(level)}</span>
  </div>
  <div class="q-meta">📋 {reports} 人报告 · 🕒 {esc(last)}</div>
  <div class="q-desc">{esc(desc)}</div>
</div>"""
        cards.append(card)

    type_buttons = ['<button class="active" data-filter="all">全部 ({})</button>'.format(len(questions))]
    for tname, _label in types_meta:
        count = len(type_groups.get(tname, []))
        if count:
            type_buttons.append(f'<button data-filter="{esc(tname)}">{esc(tname)} ({count})</button>')

    counts = ' '.join(f'<span class="stat"><strong>{len(type_groups.get(t, []))}</strong> {esc(t)}</span>' for t, _ in types_meta if type_groups.get(t))

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenAI 面试题准备 · Hello Interview 整理</title>
<meta name="description" content="OpenAI 全岗位 44 道面试题 · 题面 + 中文思路解析 · Python 解法 · System Design 架构思路">
<link rel="stylesheet" href="assets/style.css?v={CSS_HASH}">
</head>
<body>
<header class="site-header">
  <div class="container">
    <h1><a href="index.html">🧠 OpenAI 面试题准备</a></h1>
    <div class="meta">来源：hellointerview.com · {len(questions)} 题</div>
  </div>
</header>
<main class="container">
  <div class="intro">
    <h2>OpenAI 全岗位面试题（共 {len(questions)} 题）</h2>
    <p>题目来自 hellointerview.com 社区的真实候选人报告，按最近问询时间倒序排列。每题包含原始题面、中文思路解析、System Design 思路 / Python 解法、易错点。</p>
    <div class="stats">{counts}</div>
  </div>

  <div class="filter-bar">
    <span class="filter-label">按类型筛选：</span>
    {''.join(type_buttons)}
  </div>

  <div class="q-grid" id="q-grid">{''.join(cards)}</div>
</main>

<script>
document.querySelectorAll('.filter-bar button').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-bar button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const filter = btn.dataset.filter;
    document.querySelectorAll('.q-card').forEach(card => {{
      card.style.display = (filter === 'all' || card.dataset.type === filter) ? '' : 'none';
    }});
  }});
}});
</script>
</body>
</html>"""
    return html_doc


def render_detail(q, raw, analysis_md, prev_q, next_q):
    slug_id = q["slug"].rsplit("/", 1)[-1]
    title = q["title"]
    qtype = q["type"]
    level = q["level"] or "—"
    reports = q["reportedUsers"] or 0
    last = q["lastAsked"] or "—"
    source_url = q["url"]
    desc = raw.get("shortDescription") or q.get("description") or ""

    # Timeline variants
    timeline = parse_timeline(raw.get("timelineRaw") or "")
    variant_html = ""
    if timeline:
        rows = []
        for v in timeline:
            notes = " · ".join(v.get("notes") or []).strip()
            notes_html = f'<div>{esc(notes)}</div>' if notes else ""
            rows.append(f"""
<div class="variant">
  <div class="vmeta">{esc(v['date'])} · <strong>{esc(v.get('company') or '')}</strong> · {esc(v.get('level') or '')}</div>
  {notes_html}
</div>""")
        variant_html = f"""
<section class="section">
  <h2>Variants & Timeline ({len(timeline)} 条真实报告)</h2>
  <p>下面是其他候选人在不同公司被问到这题的变种描述（含本题的 OpenAI 报告以及其他公司的同题）：</p>
  <div class="variants">{''.join(rows)}</div>
</section>"""

    # Comments
    comments = parse_comments(raw.get("commentsRaw") or "")
    comments_html = ""
    if comments:
        crows = []
        for c in comments[:8]:
            crows.append(f'<div class="comment">{esc(c["body"])}</div>')
        comments_html = f"""
<section class="section">
  <h2>讨论摘要 ({len(comments)} 条)</h2>
  {''.join(crows)}
</section>"""

    # External resources
    ext = raw.get("externalLinks") or []
    ext_html = ""
    if ext:
        lis = "".join(f'<li><a href="{esc(x)}" target="_blank" rel="noopener">{esc(x)}</a></li>' for x in ext)
        ext_html = f'<section class="section"><h2>外部链接</h2><ul>{lis}</ul></section>'

    # Analysis (from markdown). Demote h2→h3, h3→h4 so they nest under section's h2.
    if analysis_md and analysis_md.strip():
        analysis_html = md_to_html(analysis_md)
        analysis_html = re.sub(r'<h4>', '<h5>', analysis_html)
        analysis_html = re.sub(r'</h4>', '</h5>', analysis_html)
        analysis_html = re.sub(r'<h3>', '<h4>', analysis_html)
        analysis_html = re.sub(r'</h3>', '</h4>', analysis_html)
        analysis_html = re.sub(r'<h2>', '<h3>', analysis_html)
        analysis_html = re.sub(r'</h2>', '</h3>', analysis_html)
    else:
        analysis_html = "<p><em>分析尚未撰写。</em></p>"

    # Prev/Next nav
    nav_prev = ""
    if prev_q:
        prev_slug = prev_q["slug"].rsplit("/", 1)[-1]
        nav_prev = f'<a href="{prev_slug}.html">← {esc(prev_q["title"])}</a>'
    else:
        nav_prev = "<span></span>"
    nav_next = ""
    if next_q:
        next_slug = next_q["slug"].rsplit("/", 1)[-1]
        nav_next = f'<a href="{next_slug}.html">{esc(next_q["title"])} →</a>'
    else:
        nav_next = "<span></span>"

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · OpenAI 面试题</title>
<link rel="stylesheet" href="../assets/style.css?v={CSS_HASH}">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.css">
</head>
<body>
<header class="site-header">
  <div class="container">
    <h1><a href="../index.html">🧠 OpenAI 面试题准备</a></h1>
    <div class="meta"><a href="../index.html">← 返回列表</a></div>
  </div>
</header>
<main class="container detail">
  <div class="breadcrumb"><a href="../index.html">所有题目</a> / {esc(qtype)} / {esc(title)}</div>
  <h1>{esc(title)}</h1>
  <div class="header-meta">
    <span class="{tag_class(qtype)}">{esc(qtype)}</span>
    <span class="tag tag-level">{esc(level)}</span>
    <span>📋 {reports} 人报告</span>
    <span>🕒 最近：{esc(last)}</span>
    <span class="external"><a href="{esc(source_url)}" target="_blank" rel="noopener">原题 ↗</a></span>
  </div>

  <section class="section">
    <h2>Problem Statement</h2>
    <p class="problem-statement">{esc(desc)}</p>
  </section>

  <section class="section">
    <h2>我的思路与解法</h2>
    {analysis_html}
  </section>

  {variant_html}
  {comments_html}
  {ext_html}

  <div class="nav-footer">
    {nav_prev}
    {nav_next}
  </div>
</main>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-core.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
</body>
</html>"""
    return html_doc


def main():
    with open(QUESTIONS_JSON) as f:
        questions = json.load(f)

    # Group by type
    type_groups = {}
    for q in questions:
        type_groups.setdefault(q["type"], []).append(q)

    # Recency sort (already done in source file, but enforce)
    month_idx = {m: i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"], 1)}
    phase_idx = {"Early": 1, "Mid": 2, "Late": 3}
    def sk(q):
        la = q.get("lastAsked") or ""
        m = re.match(r"(Early|Mid|Late)\s+(\w+),\s+(\d+)", la)
        if not m: return (0, 0, 0)
        return (int(m.group(3)), month_idx.get(m.group(2), 0), phase_idx.get(m.group(1), 0))
    recency_sorted = sorted(questions, key=sk, reverse=True)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / "questions").mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / "assets").mkdir(parents=True, exist_ok=True)

    # Copy CSS + compute content hash for cache busting
    import shutil, hashlib
    css_src = SITE / "assets" / "style.css"
    css_bytes = css_src.read_bytes()
    css_hash = hashlib.md5(css_bytes).hexdigest()[:8]
    shutil.copy(css_src, PUBLIC_DIR / "assets" / "style.css")
    # Expose for templates
    globals()['CSS_HASH'] = css_hash

    # Write index
    idx_html = render_index(questions, type_groups, recency_sorted)
    (PUBLIC_DIR / "index.html").write_text(idx_html, encoding="utf-8")
    print(f"wrote {PUBLIC_DIR / 'index.html'}")

    # Write detail pages — order them by recency, with prev/next nav linking
    for i, q in enumerate(recency_sorted):
        slug_id = q["slug"].rsplit("/", 1)[-1]
        raw_path = RAW_DIR / f"{slug_id}.json"
        if not raw_path.exists():
            print(f"  no raw data for {slug_id}; skipping")
            continue
        with open(raw_path) as f:
            raw = json.load(f)
        analysis_path = ANALYSES_DIR / f"{slug_id}.md"
        analysis_md = analysis_path.read_text(encoding="utf-8") if analysis_path.exists() else ""
        prev_q = recency_sorted[i - 1] if i > 0 else None
        next_q = recency_sorted[i + 1] if i + 1 < len(recency_sorted) else None
        detail_html = render_detail(q, raw, analysis_md, prev_q, next_q)
        out_path = PUBLIC_DIR / "questions" / f"{slug_id}.html"
        out_path.write_text(detail_html, encoding="utf-8")
    print(f"wrote {len(recency_sorted)} detail pages")

if __name__ == "__main__":
    main()
