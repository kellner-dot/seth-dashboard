# Full-stack recovery runbook (2026-10-05)

How a new Kavi gets back EVERYTHING that is in place. Secrets are NEVER
in this file — they live as named files on Seth's Google Drive; pull them
per `files/kavi-secrets-guide.md` (Drive CLI → `~/.kavi-secrets/`).

## A. This VM (Kavi runtime)

1. **Tailscale**: install, `tailscale up`. Seth authenticates the device.
   Verify: `tailscale status` shows SETHS-PC.
2. **GitHub**: `gh auth login` (device flow at github.com/login/device),
   then `gh auth setup-git`. Fallback: Kavi Push PAT on Drive.
3. **Repos**: `gh repo clone kellner-dot/seth-dashboard`,
   `gh repo clone kellner-dot/firetv-vega`.
4. **Skills** (in `~/workspace/skills/`): rvg-agent, amazon-appstore,
   routenote. RVG from the sandbox MUST go through
   `bin/pcps.py <script.ps1>` — never `bin/rvg.py` directly (the vault
   credential 403s in the sandbox).
5. **Vega SDK**: `firetv-vega/README.md` quick start
   (`vega sdk config setup --non-interactive`). Expect 0.24.x at
   `/home/hatch/vega`.
6. **socat**: install via package manager (stick tunnel).
7. **Memory**: `~/MEMORY.md` + `~/memory/` carry the durable state.
   If the VM is truly fresh and these are gone, the GitHub docs branch
   `docs/firetv-vega-app-2026-10-05` (seth-dashboard) has the session
   records to bootstrap from.

## B. Scheduled jobs (recreate if lost)

- `heartbeat` — hourly (system heartbeat)
- `kavi-mail-watch` — every 10m, owner `goal:kavi-2-0-to-kavi-6-0-stack-handoff`
- `routenote-moderation-watch` — daily ~09:52, owner
  `goal:pop-s-routenote-album-release`. STOPS on its own once the
  release goes live; notify Seth only on status change.
- `kavi-console-watcher` — every 30m (Kavi Console outbox refresh)
- `ambient-frame-sensor` — every 15m
- `agentic-feature-tour` — daily
Definitions live under `~/workspace/cron.d/` and the goal workspaces;
recreate with the cron tools, don't hand-edit the files.

## C. SETHS-PC

Runs on Seth's PC; code in the repos:
- **KaviTV relay v2.0** (port 8100) — source `seth-dashboard/kavitv/`
- **XC bridge** (port 8880) — serves KaviTV to Flix Pro
- **Emby Server** 4.10.1.0 (API key on Drive)
- **Tailscale subnet route** `10.0.0.0/24` — re-approve in the Tailscale
  admin console if the PC is reinstalled (`IPEnableRouter=1` +
  `tailscale up --advertise-routes=10.0.0.0/24`)
- **RVG agent** — remote access to the PC

## D. Fire Stick

- **Devmode**: enable on the stick, `vega devmode enable-device
  --code <CODE>` (codes expire in ~5 min; see
  `firetv-vega/docs/DEVMODE.md`)
- **Reinstall apps**: rebuild each `.vpkg` from source or check Drive
  for saved builds; install via `vda`/on-device `vpm install`
- **Reboot after install** so the launcher re-enumerates tiles
  (no tile = app can't be opened/pinned)
- **Verify**: `vpm list packages` → all 16 `com.kellner.*` apps
  (KaviTV, Mission Control, KaviTV Console, RVG Agent, Emby Theater x2,
  IPTV Player, Cloud Drive, Planner, Podcasts, News, Weather, Gallery,
  Radio, Torrent, Pulse, Passman)
- Stick link from VM: socat tunnel + `vda connect 127.0.0.1:15555`
  (full commands in the continuity note)

## E. Accounts & services

- **Gmail** `sethryankellner@gmail.com` — kavi-mail protocol v2.1 lives
  here; Kavi may send kavi-mail without per-message approval
- **Amazon developer** (vendor "Seth Kellner Photography") — Appstore
  + Live App Testing for the Vega app
- **Tailscale admin** — route approvals, ACLs
- **RouteNote** (ksethco) — "Piano" release pending moderation
- **SoundOn** — Tuff Old Bird dispute + Digital Deity removal, awaiting replies

## F. In-flight work (do not lose)

- KaviTV clean rebuild (Emby ID re-inventory)
- KaviTV Vega app upgrade (build agent active 2026-10-05)
- RouteNote moderation watch (daily cron)
- SoundOn email threads (awaiting replies)
- Samuel Warner disability-hearing prep call — Oct 22

## Inventory snapshot (2026-10-05)

VM: Tailscale joined, gh authed (kellner-dot), Vega SDK 0.24.12112,
socat, repos + skills. Stick: devmode on, 16 kellner apps.
PC: relay v2.0, XC bridge, Emby, subnet router. GitHub: session docs
on branch `docs/firetv-vega-app-2026-10-05`.
