#!/usr/bin/env python3
"""Add Muse card to Mission Control dashboard (index.html + tv.html)."""
import re, sys

MUSE_ICON = '''  muse: `<svg viewBox="0 0 48 48"><defs><linearGradient id="muBg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f5f0e8"/><stop offset="1" stop-color="#e8ddd0"/></linearGradient></defs><rect x="3" y="3" width="42" height="42" rx="11" fill="url(#muBg)"/><rect x="3" y="3" width="42" height="13" rx="11" fill="#fff" opacity=".4"/><g fill="#b85c38"><path d="M24 8c-5.2 0-9.4 3.4-10.9 8.1L8 28.5c-.5 2.3.6 4.5 2.7 5.3 1 .4 2.1.5 3.1.2l2.4 3.6c.6.9 1.8.9 2.4 0l2.4-3.6 2.4 3.6c.6.9 1.8.9 2.4 0l2.4-3.6c1 .3 2.1.2 3.1-.2 2.1-.8 3.2-3 2.7-5.3l-5.1-12.4C33.4 11.4 29.2 8 24 8z"/><circle cx="19" cy="24" r="2.2" fill="#f5f0e8"/><circle cx="29" cy="24" r="2.2" fill="#f5f0e8"/><path d="M19 30c2 1.5 8 1.5 10 0" stroke="#f5f0e8" stroke-width="2" fill="none" stroke-linecap="round"/></g><rect x="3" y="3" width="42" height="42" rx="11" fill="none" stroke="#b85c38" stroke-width="1.4" opacity=".5"/></svg>`,'''

MUSE_CSS = '''  .poster.k-muse{--pbg:linear-gradient(135deg,#7a4a2b,#1a1008);}'''

MUSE_CARD_FN = '''
function museCard(){
  const body =
      rowline('\\u{1F9E0} Assistant', '<span class="ok">\\u25CF Kavi</span>')
    + rowline('\\u{1F4AC} Chat', '<a class="ext" href="https://claude.ai" target="_blank">claude.ai \\u2197</a>')
    + rowline('\\u2728; Ask', '<span class="dim">anything, anytime</span>');
  return {id:'muse', url:'https://claude.ai', cls:'k-muse', icon:'muse', title:'Muse', sub:'chat with kavi',
    dot:`<span class="dotlive on"></span>`, pill:pill('on','ai assistant'), body, detail:body};
}
'''

def patch(path):
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    orig = html

    # 1. Add muse icon to ICONS (before the closing "};" of ICONS)
    if 'muse: `' not in html:
        html = html.replace(
            "  chat: `<svg viewBox=\"0 0 48 48\">",
            MUSE_ICON + "\n" + "  chat: `<svg viewBox=\"0 0 48 48\">",
            1
        )

    # 2. Add CSS gradient for k-muse
    if '.poster.k-muse' not in html:
        html = html.replace(
            "  .poster.k-act{--pbg:linear-gradient(135deg,#3a3f1a,#12100a);}",
            "  .poster.k-act{--pbg:linear-gradient(135deg,#3a3f1a,#12100a);}\n" + MUSE_CSS,
            1
        )

    # 3. Add museCard() function before githubCard
    if 'function museCard()' not in html:
        html = html.replace(
            "function githubCard(g){",
            MUSE_CARD_FN.strip() + "\n\nfunction githubCard(g){",
            1
        )

    # 4. Add to ops row (first position for prominence)
    if "museCard()" not in html.split("const ops=[")[1].split("];")[0] if "const ops=[" in html else True:
        html = html.replace(
            "  const ops=[\n    githubCard(j.github),",
            "  const ops=[\n    museCard(),\n    githubCard(j.github),",
            1
        )

    if html != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"PATCHED {path}")
    else:
        print(f"NO CHANGES {path} (already patched?)")

for p in sys.argv[1:]:
    patch(p)
