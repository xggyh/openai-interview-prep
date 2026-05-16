#!/usr/bin/env python3
"""Scrape question list metadata from a hellointerview filter page via Arc.

Usage:
    ARC_TAB_ID=... python3 scrape_list.py <url> <out.json>
"""
import sys, time, subprocess, json, ast, os
from pathlib import Path

ARC_TAB_ID = os.environ["ARC_TAB_ID"]

LIST_JS = r"""(()=>{const out=[];const seen=new Set();const links=document.querySelectorAll('a[href*="/community/questions/"]');links.forEach(a=>{const href=a.getAttribute('href');if(!href||href.includes('#'))return;const slug=href.split('?')[0];if(!slug.match(/\/community\/questions\/[^/]+\/[a-z0-9]+/))return;if(seen.has(slug))return;seen.add(slug);let card=a;for(let i=0;i<8&&card;i++){const t=(card.innerText||'').trim();if(t.match(/Reported by\s+\d/)&&t.length>50&&t.length<3000)break;card=card.parentElement;}if(!card)return;const text=card.innerText.trim();const lines=text.split('\n');const title=a.textContent.trim()||(lines[0]||'');const type=lines[1]||'';const level=lines[2]||'';const rm=text.match(/Reported by\s+([\d,]+)\s+(?:user|users)\s*•\s*Last Asked\s+([^\n]+)/);const descLines=lines.slice(3).filter(l=>l&&!l.match(/^Reported by|^Were You|^View Details|^\+\d+ others/));const desc=descLines.join(' ').trim();out.push({title,slug,url:'https://www.hellointerview.com'+slug,type,level,reportedUsers:rm?+rm[1].replace(/,/g,''):null,lastAsked:rm?rm[2].trim():null,description:desc});});return JSON.stringify({count:out.length,items:out});})()"""

def navigate(url):
    script = f'''
tell application "Arc"
    repeat with w from 1 to count windows
        repeat with tt from 1 to count tabs of window w
            if id of tab tt of window w is "{ARC_TAB_ID}" then
                set URL of tab tt of window w to "{url}"
                return "ok"
            end if
        end repeat
    end repeat
    return "TAB_NOT_FOUND"
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)

def exec_js(js):
    js_esc = js.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''
tell application "Arc"
    repeat with w from 1 to count windows
        repeat with tt from 1 to count tabs of window w
            if id of tab tt of window w is "{ARC_TAB_ID}" then
                return execute tab tt of window w javascript "{js_esc}"
            end if
        end repeat
    end repeat
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def main():
    url, out_path = sys.argv[1], sys.argv[2]
    navigate(url)
    time.sleep(5)
    raw = exec_js(LIST_JS)
    # AppleScript wraps in "..."; unwrap
    if raw.startswith('"'):
        data_str = ast.literal_eval(raw)
    else:
        data_str = raw
    parsed = json.loads(data_str)
    Path(out_path).write_text(json.dumps(parsed['items'], indent=2, ensure_ascii=False))
    print(f"  saved {len(parsed['items'])} items to {out_path}")

if __name__ == "__main__":
    main()
