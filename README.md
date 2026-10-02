# Seth's Dashboard

Personal homepage / project hub for Seth — built for GitHub Pages.

## Files

- `index.html` — the hub: Music, Tech Projects, Links
- `style.css` — dark techno theme, responsive, no frameworks
- `script.js` — scroll-reveal + a tiny easter egg
- `CNAME` — placeholder; replace with the real custom domain when Seth picks one

## Deploy to GitHub Pages

1. Create a repo (e.g. `kellner-dot/seth` or `kellner-dot.github.io`)
2. Push these files to `main`
3. Repo → Settings → Pages → Source: Deploy from branch, `main`, `/ (root)`
4. If using a custom domain, replace the `CNAME` file contents with it
5. Keep it private-safe: nothing here contains secrets or personal identifiers beyond what's already public

## Notes

- Pure HTML/CSS/JS — no build step, no dependencies, no tracking
- Stats (channels, GB) are snapshots; update the numbers in `index.html` when they change
- The "Latest single" card is marked `.highlight` so the current release always pops
