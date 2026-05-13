#!/usr/bin/env python3
"""Scrape full question detail pages from hellointerview.com via Arc + AppleScript."""

import json, subprocess, time, ast, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
QUESTIONS_JSON = ROOT / "openai-interview-questions.json"
RAW_DIR = ROOT / "site" / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

EXTRACT_JS = r"""
(()=>{
  // Click any "Show N More" buttons to expand timeline + comments first
  const clicks = [];
  document.querySelectorAll('button').forEach(b => {
    const t = (b.textContent || '').trim();
    if (/^Show \d+ More/i.test(t) || /Show More/i.test(t)) {
      try { b.click(); clicks.push(t); } catch(e) {}
    }
  });
  return JSON.stringify({clicked: clicks});
})()
"""

EXTRACT_DATA_JS = r"""
(()=>{
  const out = {};
  // Title
  const h1 = document.querySelector('h1');
  out.title = h1 ? h1.textContent.trim() : null;

  // Short description: usually the first <p> right after h1
  let desc = null;
  if (h1) {
    let el = h1.nextElementSibling;
    while (el && el.tagName !== 'P' && !el.querySelector('p')) el = el.nextElementSibling;
    if (el) {
      const p = el.tagName === 'P' ? el : el.querySelector('p');
      desc = p ? p.textContent.trim() : null;
    }
  }
  out.shortDescription = desc;

  // Full visible body text (raw)
  out.bodyText = document.body.innerText;

  // Extract timeline entries — look for the "Question Timeline" section
  // Heuristic: find element containing the text "Question Timeline" then collect all
  // subsequent block elements with date/company/level patterns
  const allText = document.body.innerText;
  const timelineMatch = allText.match(/Question Timeline[\s\S]*?(?=Comments|$)/);
  out.timelineRaw = timelineMatch ? timelineMatch[0] : null;

  // Extract comments section text
  const commentsMatch = allText.match(/Comments[\s\S]*?(?=Questions\nMeta SWE|$)/);
  out.commentsRaw = commentsMatch ? commentsMatch[0] : null;

  // Get all <a> hrefs that look like external code links (e.g., leetcode)
  const externalLinks = [];
  document.querySelectorAll('a[href]').forEach(a => {
    const href = a.href;
    if (href && (href.includes('leetcode.com') || href.includes('github.com')) && !externalLinks.includes(href)) {
      externalLinks.push(href);
    }
  });
  out.externalLinks = externalLinks;

  return JSON.stringify(out);
})()
"""

def osascript_navigate(url: str):
    """Navigate Arc's active tab to URL."""
    script = f'''
tell application "Arc"
    tell active tab of front window
        set URL to "{url}"
    end tell
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)

def osascript_exec(js: str) -> str:
    """Execute JS in active Arc tab via AppleScript, return result as raw string."""
    # AppleScript needs JS escaped inside double quotes; double quotes inside JS become \"
    js_escaped = js.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Arc"
    tell active tab of front window
        return execute javascript "{js_escaped}"
    end tell
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    return r.stdout.strip()

def osascript_ready() -> str:
    return osascript_exec("document.readyState")

def parse_applescript_value(raw: str):
    """AppleScript returns strings as "..." with escapes; ast.literal_eval handles it."""
    if not raw:
        return None
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw

def scrape_one(q: dict, delay_load: float = 4.0) -> dict:
    url = q["url"]
    osascript_navigate(url)
    time.sleep(delay_load)
    # Wait for readyState=complete (max 10s)
    for _ in range(20):
        rs_raw = osascript_ready()
        rs = parse_applescript_value(rs_raw)
        if rs == "complete":
            break
        time.sleep(0.5)
    # Click "Show More" buttons to expand
    osascript_exec(EXTRACT_JS)
    time.sleep(1.2)
    # Click again in case there's a second "Show More" revealed
    osascript_exec(EXTRACT_JS)
    time.sleep(0.8)
    # Extract data
    raw = osascript_exec(EXTRACT_DATA_JS)
    data_str = parse_applescript_value(raw)
    if not data_str:
        return {"error": "empty extraction", "meta": q}
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError as e:
        return {"error": f"json decode: {e}", "raw": data_str[:500], "meta": q}
    data["meta"] = q
    return data

def main():
    with open(QUESTIONS_JSON) as f:
        questions = json.load(f)
    print(f"Scraping {len(questions)} questions...")
    start = time.time()
    for i, q in enumerate(questions, 1):
        slug_id = q["slug"].rsplit("/", 1)[-1]
        out_path = RAW_DIR / f"{slug_id}.json"
        if out_path.exists() and "--force" not in sys.argv:
            print(f"[{i:2}/{len(questions)}] SKIP (cached): {q['title'][:60]}")
            continue
        print(f"[{i:2}/{len(questions)}] scraping: {q['title'][:60]}...", flush=True)
        try:
            data = scrape_one(q)
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            bt_len = len(data.get("bodyText", "") or "")
            print(f"           saved {out_path.name} ({bt_len} chars body)")
        except subprocess.TimeoutExpired:
            print(f"           TIMEOUT, skipping")
        except Exception as e:
            print(f"           ERROR: {e}")
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")

if __name__ == "__main__":
    main()
