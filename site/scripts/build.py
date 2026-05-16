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

# Unified multi-company source (preferred). Falls back to single-company file
# for compatibility.
UNIFIED_JSON = SITE / "data" / "questions.json"
LEGACY_JSON = ROOT / "openai-interview-questions.json"
QUESTIONS_JSON = UNIFIED_JSON if UNIFIED_JSON.exists() else LEGACY_JSON

# Company display order on the index page
COMPANY_ORDER = ["OpenAI", "Google"]

# Per-company brand color (used for the company badge tint)
COMPANY_COLOR = {
    "OpenAI": "#10a37f",   # OpenAI green
    "Google": "#4285f4",   # Google blue
    "Meta":   "#1877f2",
    "Amazon": "#ff9900",
    "Anthropic": "#d97706",
}

# Questions that have been rewritten in extended teaching-style depth.
# These show a 📚 badge and have a dedicated filter.
DEEP_DIVE_SLUGS = {
    # Google Senior System Design (11 questions, rewritten 2026-05-16)
    "cm9auesuf00ioad072gonjah8",  # Distributed Denylist System
    "cm7honmgk0278imqn03o95rtg",  # Trending Hashtags System
    "cm4szwvht003pnqlrkhad2xjd",  # Ticket Booking System
    "cm4t1rgrn005988ilm7ct8ma1",  # Image Uploader
    "cmkxbumw501pk08ad4wrda4pv",  # Large Model File Distribution
    "cm6jx0wxh016bui4b2oqtwudo",  # Logger System
    "cm6jwhimp0093dar9n0eo4lvt",  # Server Health Monitoring
    "cm6i9u0oh00rmjx73lr1pjtlu",  # Navigation/Mapping
    "cmgs26zx800vx08ad6f8ncnxh",  # Global VM Monitoring
    "cmdj4mw0801blad0810r3tfos",  # Slowest Query System
    "cmi3quwzg02mg07ad9blftp07",  # Fast Food Restaurant Chain
    # Long-form guides
    "g-openai-fde-takehome-convfinqa",  # OpenAI FDE Take-home Walkthrough
}

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

        # Table (GitHub-flavored)
        # Header row: |c1|c2|c3|  followed by separator |---|---|---|
        if stripped.startswith("|") and i + 1 < n:
            sep_line = lines[i + 1].strip()
            if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", sep_line):
                # Parse header
                header_cells = [c.strip() for c in stripped.strip("|").split("|")]
                # Parse alignment from separator
                sep_cells = [c.strip() for c in sep_line.strip("|").split("|")]
                aligns = []
                for s in sep_cells:
                    if s.startswith(":") and s.endswith(":"):
                        aligns.append("center")
                    elif s.endswith(":"):
                        aligns.append("right")
                    elif s.startswith(":"):
                        aligns.append("left")
                    else:
                        aligns.append(None)
                i += 2  # skip header + separator
                # Body rows
                body_rows = []
                while i < n and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    body_rows.append(cells)
                    i += 1
                # Render
                def cell_html(tag, content, align):
                    style = f' style="text-align:{align}"' if align else ""
                    return f"<{tag}{style}>{md_inline(content)}</{tag}>"
                thead = "<tr>" + "".join(
                    cell_html("th", h, aligns[k] if k < len(aligns) else None)
                    for k, h in enumerate(header_cells)
                ) + "</tr>"
                tbody = "".join(
                    "<tr>" + "".join(
                        cell_html("td", c, aligns[k] if k < len(aligns) else None)
                        for k, c in enumerate(row)
                    ) + "</tr>" for row in body_rows
                )
                out.append(f'<table class="md-table"><thead>{thead}</thead><tbody>{tbody}</tbody></table>')
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


def render_index(questions, type_groups, company_groups, recency_sorted):
    """Render index.html with company + type filters."""
    types_meta = [
        ("Guide", "Guide（专题文章）"),
        ("Coding", "Coding 题（算法 / LLD 编码）"),
        ("System Design", "System Design 题（架构设计）"),
        ("Googlyness", "Googlyness（Google 行为面试）"),
        ("People Management", "People Management（管理向）"),
        ("Behavioral", "Behavioral（行为面试）"),
        ("Low Level Design", "Low Level Design（OOP / 类设计）"),
        ("Product Architecture", "Product Architecture（产品架构）"),
        ("Mobile System Design", "Mobile System Design（移动端设计）"),
        ("ML System Design", "ML System Design（机器学习系统）"),
        ("Technical Project Retrospective", "Tech Project Retrospective（项目复盘）"),
    ]
    cards = []
    for q in recency_sorted:
        slug_id = q["slug"].rsplit("/", 1)[-1]
        href = f"questions/{slug_id}.html"
        qtype = q["type"]
        companies = q.get("companies", {})
        company_list = [c for c in COMPANY_ORDER if c in companies] + \
                       [c for c in companies if c not in COMPANY_ORDER]
        # Aggregate reports across companies for display
        total_reports = sum((companies[c].get("reportedUsers") or 0) for c in companies)
        # Most recent last-asked across companies
        most_recent = max(
            ((companies[c].get("lastAsked") or "") for c in companies),
            key=lambda la: _recency_key(la),
        )
        # Use the union of levels seen, picking shortest as primary tag
        levels = sorted({(companies[c].get("level") or "—") for c in companies}, key=len)
        level_tag = levels[0] if levels else "—"

        desc = (q.get("description") or "").strip()
        if len(desc) > 180:
            desc = desc[:180].rsplit(" ", 1)[0] + "…"

        company_badges = []
        for c in company_list:
            color = COMPANY_COLOR.get(c, "#57606a")
            n = companies[c].get("reportedUsers") or 0
            company_badges.append(
                f'<span class="company-badge" style="--c:{color}" title="{esc(c)}: {n} 人报告">{esc(c)} {n}</span>'
            )

        # Deep dive badge for teaching-style rewritten questions
        is_deep = slug_id in DEEP_DIVE_SLUGS
        deep_badge = '<span class="deep-badge" title="教学版深度讲解：概念铺垫 + 架构推演 + 45min 面试节奏 + Follow-up 演练">📚 教学版</span>' if is_deep else ''

        data_companies = "|".join(company_list)
        data_deep = "1" if is_deep else "0"
        card = f"""
<div class="q-card{' is-deep' if is_deep else ''}" data-type="{esc(qtype)}" data-companies="{esc(data_companies)}" data-deep="{data_deep}">
  <a class="q-title" href="{href}">{esc(q['title'])}</a>
  <div class="q-tags">
    <span class="{tag_class(qtype)}">{esc(qtype)}</span>
    <span class="tag tag-level">{esc(level_tag)}</span>
    {deep_badge}
    {''.join(company_badges)}
  </div>
  <div class="q-meta">📋 {total_reports} 人报告 · 🕒 最近 {esc(most_recent or '—')}</div>
  <div class="q-desc">{esc(desc)}</div>
</div>"""
        cards.append(card)

    # Company tabs
    company_tabs = ['<button class="active" data-cfilter="all">全部公司 ({})</button>'.format(len(questions))]
    for cname in COMPANY_ORDER:
        if cname in company_groups:
            company_tabs.append(
                f'<button data-cfilter="{esc(cname)}" style="--c:{COMPANY_COLOR.get(cname, "#57606a")}">{esc(cname)} ({len(company_groups[cname])})</button>'
            )

    # Type filter buttons
    type_buttons = ['<button class="active" data-tfilter="all">全部类型 ({})</button>'.format(len(questions))]
    for tname, _label in types_meta:
        count = len(type_groups.get(tname, []))
        if count:
            type_buttons.append(f'<button data-tfilter="{esc(tname)}">{esc(tname)} ({count})</button>')

    # Deep dive filter (toggle button)
    deep_count = sum(1 for q in questions if q["slug"].rsplit("/", 1)[-1] in DEEP_DIVE_SLUGS)
    deep_tabs = [
        '<button class="active" data-dfilter="all">全部</button>',
        f'<button data-dfilter="deep">📚 教学版深度讲解 ({deep_count})</button>',
    ]

    counts = ' '.join(
        f'<span class="stat"><strong>{len(type_groups.get(t, []))}</strong> {esc(t)}</span>'
        for t, _ in types_meta if type_groups.get(t)
    )

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>面试题准备 · OpenAI / Google · Hello Interview 整理</title>
<meta name="description" content="OpenAI / Google 面试题汇总 · 题面 + 中文思路解析 · Python 解法 · System Design 架构思路">
<link rel="stylesheet" href="assets/style.css?v={CSS_HASH}">
</head>
<body>
<header class="site-header">
  <div class="container">
    <h1><a href="index.html">🧠 面试题准备</a></h1>
    <div class="meta">来源：hellointerview.com · {len(questions)} 题 · OpenAI + Google</div>
  </div>
</header>
<main class="container">
  <div class="intro">
    <h2>面试题汇总（共 {len(questions)} 题）</h2>
    <p>题目来自 hellointerview.com 社区的真实候选人报告。每题包含原始题面、中文思路解析、System Design 思路 / Python 解法、易错点。按公司 / 类型筛选，按最近问询时间倒序。</p>
    <div class="stats">{counts}</div>
  </div>

  <div class="filter-bar">
    <span class="filter-label">公司：</span>
    {''.join(company_tabs)}
  </div>
  <div class="filter-bar">
    <span class="filter-label">类型：</span>
    {''.join(type_buttons)}
  </div>
  <div class="filter-bar">
    <span class="filter-label">深度：</span>
    {''.join(deep_tabs)}
  </div>

  <div class="q-grid" id="q-grid">{''.join(cards)}</div>
</main>

<script>
const state = {{ cfilter: 'all', tfilter: 'all', dfilter: 'all' }};
function applyFilters() {{
  document.querySelectorAll('.q-card').forEach(card => {{
    const companies = (card.dataset.companies || '').split('|');
    const matchC = state.cfilter === 'all' || companies.includes(state.cfilter);
    const matchT = state.tfilter === 'all' || card.dataset.type === state.tfilter;
    const matchD = state.dfilter === 'all' || (state.dfilter === 'deep' && card.dataset.deep === '1');
    card.style.display = (matchC && matchT && matchD) ? '' : 'none';
  }});
}}
document.querySelectorAll('button[data-cfilter]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('button[data-cfilter]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.cfilter = btn.dataset.cfilter;
    applyFilters();
  }});
}});
document.querySelectorAll('button[data-tfilter]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('button[data-tfilter]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.tfilter = btn.dataset.tfilter;
    applyFilters();
  }});
}});
document.querySelectorAll('button[data-dfilter]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('button[data-dfilter]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.dfilter = btn.dataset.dfilter;
    applyFilters();
  }});
}});
</script>
</body>
</html>"""
    return html_doc


_MONTH_IDX = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"], 1)}
_PHASE_IDX = {"Early": 1, "Mid": 2, "Late": 3}

def _recency_key(la: str | None) -> tuple:
    if not la: return (0, 0, 0)
    m = re.match(r"(Early|Mid|Late)\s+(\w+),\s+(\d+)", la)
    if not m: return (0, 0, 0)
    return (int(m.group(3)), _MONTH_IDX.get(m.group(2), 0), _PHASE_IDX.get(m.group(1), 0))


def render_detail(q, raw, analysis_md, prev_q, next_q):
    slug_id = q["slug"].rsplit("/", 1)[-1]
    title = q["title"]
    qtype = q["type"]
    companies = q.get("companies", {})
    source_url = q["url"]
    desc = raw.get("shortDescription") or q.get("description") or ""

    # Build per-company chips
    company_list = [c for c in COMPANY_ORDER if c in companies] + \
                   [c for c in companies if c not in COMPANY_ORDER]
    company_chips = []
    for c in company_list:
        color = COMPANY_COLOR.get(c, "#57606a")
        info = companies[c]
        n = info.get("reportedUsers") or 0
        lvl = info.get("level") or "—"
        la = info.get("lastAsked") or "—"
        company_chips.append(
            f'<span class="company-chip" style="--c:{color}">'
            f'<strong>{esc(c)}</strong> · {esc(lvl)} · 📋 {n} · 🕒 {esc(la)}</span>'
        )
    # Primary level (shortest range across companies) for breadcrumb tag
    levels = sorted({(info.get("level") or "—") for info in companies.values()}, key=len)
    primary_level = levels[0] if levels else "—"

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

    # Deep-dive banner at top of detail page
    is_deep = slug_id in DEEP_DIVE_SLUGS
    deep_banner = ''
    if is_deep:
        deep_banner = '''
  <div class="deep-banner">
    <span class="deep-badge-large">📚 教学版深度讲解</span>
    <span class="deep-banner-text">这道题已重写为新手友好的完整教学版：含概念铺垫、需求拆解、容量估算、架构 step-by-step 推演、组件深挖、45 分钟面试节奏、样板讲解稿、Follow-up Q&amp;A、易错点 + 加分项。约 600 行。</span>
  </div>'''

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 面试题准备</title>
<link rel="stylesheet" href="../assets/style.css?v={CSS_HASH}">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.css">
</head>
<body>
<header class="site-header">
  <div class="container">
    <h1><a href="../index.html">🧠 面试题准备</a></h1>
    <div class="meta"><a href="../index.html">← 返回列表</a></div>
  </div>
</header>
<main class="container detail">
  <div class="breadcrumb"><a href="../index.html">所有题目</a> / {esc(qtype)} / {esc(title)}</div>
  <h1>{esc(title)}</h1>{deep_banner}
  <div class="header-meta">
    <span class="{tag_class(qtype)}">{esc(qtype)}</span>
    <span class="tag tag-level">{esc(primary_level)}</span>
    <span class="external"><a href="{esc(source_url)}" target="_blank" rel="noopener">原题 ↗</a></span>
  </div>
  <div class="company-chips">{''.join(company_chips)}</div>

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

    # Normalize: legacy single-company format has flat reportedUsers/lastAsked/level.
    # Convert it into {companies: {OpenAI: {...}}} structure.
    for q in questions:
        if "companies" not in q:
            q["companies"] = {
                "OpenAI": {
                    "level": q.get("level"),
                    "reportedUsers": q.get("reportedUsers"),
                    "lastAsked": q.get("lastAsked"),
                }
            }

    # Group by type and company
    type_groups: dict[str, list] = {}
    company_groups: dict[str, list] = {}
    for q in questions:
        type_groups.setdefault(q["type"], []).append(q)
        for c in q.get("companies", {}):
            company_groups.setdefault(c, []).append(q)

    # Recency sort by MAX lastAsked across all companies
    def sk(q):
        keys = [_recency_key(c.get("lastAsked")) for c in q.get("companies", {}).values()]
        return max(keys) if keys else (0, 0, 0)
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
    idx_html = render_index(questions, type_groups, company_groups, recency_sorted)
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
