# Networking Savant — Tricks & Patterns (2026-10-05)

GitHub-first research for Seth's setup: tailnet with SETHS-PC (Windows, subnet
router for 10.0.0.0/24), Razr (Android), iPhone, MacBook Air, muse VMs, and a
Fire TV Stick 4K Select (Vega OS, NOT on the tailnet).

Confidence: **[O]** verified-official · **[C]** verified-community (real
homelabbers, tested) · **[P]** plausible, treat as unverified.

---

## 1. tsnet embedding patterns (Go)

**Auth order matters.** `tsnet.Server` tries, in order: `Server.AuthKey` →
`TS_AUTHKEY` → `TS_AUTH_KEY` → OAuth client secret → workload identity
federation → interactive login URL. **[C]**
— https://github.com/usetemi/skills/blob/HEAD/skills/tailscale/references/containers-tsnet.md (2026-10-01)

**Stale state dir silently keeps the old identity.** If the node already
enrolled in `Dir`, the auth key is ignored ("Authkey is set; but state is ...
Ignoring authkey") unless `TSNET_FORCE_LOGIN=1`. Default `Dir` is per-binary
under `os.UserConfigDir` — ephemeral in containers and unresolvable when
`$HOME`/`$XDG_CONFIG_HOME` is unset. Always set `Dir` explicitly to a
persistent path. **[C]** — same source.

**Ephemeral + 5-minute auth key = self-cleaning node.** Provision via the
Tailscale API with `reusable:false, ephemeral:true, preauthorized:true`,
`tags:[]` (empty tags = user-owned node), `expirySeconds:300`. Node vanishes
when the program exits. **[C]**
— https://github.com/jesssullivan/jesssullivan.github.io/blob/HEAD/src/posts/2026-02-26-bootstrapping-aperture-config-with-tsnet.md (2026-02-26)

**Exit node from embedded code.** `lc, _ := srv.LocalClient()` then
`lc.EditPrefs(ctx, &ipn.MaskedPrefs{Prefs: ipn.Prefs{ExitNodeID: "nodeid"},
ExitNodeIDSet: true})`. Dials outside the tailnet then route via exit node;
tailnet dials unaffected. **[O]**
— https://github.com/tailscale/tailscale/blob/HEAD/tsnet/README.md (2026-09-30)

**Multiple nodes in one process.** Each `tsnet.Server` is an independent node —
give each a unique `Dir` and `Hostname`. **[O]** — same source.

**WhoIs auth instead of tokens.** `srv.LocalClient().WhoIs(ctx,
r.RemoteAddr)` returns the caller's tailnet identity; middleware allows only
your login and 403s everything else. No token to paste, pair, or leak. Caveat:
for tagged source nodes the creator login is stripped — identify by tags/node
name. **[C]**
— https://github.com/viminizer/remux/blob/HEAD/docs/plan.md (2026-09-15);
https://github.com/bscott/rdc/blob/HEAD/docs/architecture.md (2026-09-14)

**`ListenTLS(":443")` = free real HTTPS.** Tailscale issues/renews the cert for
`<node>.<tailnet>.ts.net` — gives you a secure context with zero setup (this
is what makes PWA install/service workers work in the remux project). Nothing
listens on a real interface: unreachable except via tailnet *by construction*.
**[C]** — remux plan, same as above.

**`ListenFunnel` = embedded public HTTPS.** One call, valid TLS cert, public
`https://<name>.<tailnet>.ts.net`. **[O]**
— https://github.com/tailscale-dev/tailscale-dev/blob/HEAD/data/blog/embedded-funnel.mdx

**`ListenService` needs a tagged node + service approval** (`ErrUntaggedServiceHost`
otherwise); `ListenSSH` needs `import _ "tailscale.com/feature/ssh"`. **[C]**
— usetemi/skills containers-tsnet.md.

**TCP-only.** tsnet runs a gVisor userspace stack: no UDP/ICMP, ~50–200 ms
extra via DERP, and real memory overhead — relevant on the 1 GB Vega stick.
**[C]**
— https://github.com/mlorentedev/ts-bridge/blob/HEAD/docs/adr/adr-001-tsnet-userspace.md (2026-03-28)

**Python bindings are a dead end (for now).** `tailscale/libtailscale` has
experimental pybind11 bindings (v0.0.1, not on PyPI); build reported broken
since mid-2025 (issues #7920, #14178). For Python today: run `tailscaled` as a
sidecar and talk to its local API socket. **[C]**
— https://github.com/daftdoki/research/blob/HEAD/python-tsnet-research/README.md (2026-10-01)

**Perf note:** tailscale_dart 0.5.0 attaches caller identity at accept time via
an in-memory netmap index (~80 ns, not a per-accept LocalAPI round-trip), and
its loopback whois fast path cut 40 ms → 0.3 ms. If you build a hot path that
identifies every connection, mirror this: resolve identity once, cache it.
**[C]** — https://github.com/danreynolds/tailscale_dart/blob/HEAD/CHANGELOG.md

---

## 2. Tailscale Serve / Funnel — advanced

**Modes:** `--https` (default), `--http` (serve only), `--tcp` (raw TCP
forwarder — no TLS termination, no identity headers), `--tls-terminated-tcp`,
`--set-path` (mount backend under a sub-path), `--proxy-protocol=1|2` (1.92.1+,
so TCP backends learn the real client IP), `--accept-app-caps` (1.92+, forwards
tailnet ACL app capabilities), `--service` (serve on a virtual service IP).
**[C]** — https://github.com/vincenthanxiaodu/oh-my-term/blob/HEAD/docs/research/connectivity.md (tailscale 1.98.9, 2026-08)

```bash
tailscale serve --bg --https=443 --set-path=/api http://127.0.0.1:4000
tailscale serve --bg --tcp=5432 tcp://127.0.0.1:5432
```

**Identity headers:** Serve injects `Tailscale-User-Login`,
`Tailscale-User-Name`, `Tailscale-User-Profile-Pic` on proxied HTTP. NOT set
for tagged sources, Funnel, or TCP modes. Empty login = unauthenticated, never
"anonymous OK". A backend that trusts these headers **must listen on localhost
only** — otherwise direct callers can forge them. **[C]**
— https://github.com/usetemi/skills/blob/HEAD/skills/tailscale/references/expose-services.md (2026-10-01)

**The paranoid-correct pattern (vyre):** terminate TLS yourself on the tailnet
interface and identify each connection by its source IP via `tailscale whois`;
never read identity headers. "The source address of a packet that arrived over
WireGuard is the one thing a local non-root process cannot fake." **[C]**
— https://github.com/vyre-ai/vyre/blob/HEAD/docs/adr/0002-network-and-identity.md (2026-09-29)

**`--bg` persists; without it the serve dies with the shell.** Disable ONE
handler by repeating the original command with `off` appended —
`tailscale serve reset` kills *everything*, including unrelated handlers. **[C]**
— usetemi/skills expose-services.md.

**Funnel TLS ports are only 443, 8443, 10000** and it needs the `funnel` node
attribute plus admin enablement. **[C]**
— https://github.com/chere3/hermes-automation-stack/blob/HEAD/skills/devops/tailscale-service-publishing/SKILL.md (2026-09-12)

---

## 3. Subnet routers, exit nodes, WoL

**`tailscale set` REPLACES advertised routes — it does not append.** Issuing
`--advertise-routes` and `--advertise-exit-node` separately silently drops
whichever came first. Always one command:
`tailscale set --advertise-routes=192.168.1.0/24 --advertise-exit-node`. **[C]**
— https://github.com/sshindow/homelab-nas/blob/HEAD/docs/tailscale-exit-node.md (2026-09-15)

**Advertising ≠ approved.** `tailscale status` shows the advertisement either
way; a route only works once approved in the admin console. **[C]**
— https://github.com/pironex9/homelab/blob/HEAD/docs/k3s/05_Wake_on_LAN.md (2026-09-30)

**Wake-on-LAN over the tailnet:** a magic packet is a link-local broadcast —
broadcasts don't route. It must be sent by an always-on device on the same
segment, reachable over the tailnet (e.g. `ssh user@always-on-node wake-nodes`).
**[C]** — https://github.com/baakhoff/homelab/blob/HEAD/docs/network.md (2026-10-01)

**Phone as exit node:** TailSocks (third-party Android client, v4.0.0) has a
"run as exit node" switch — the Razr can be the tailnet's exit node while
traveling. Pair with `--exit-node-allow-lan-access` on clients so LAN stays
reachable when an exit node is active. **[C]**
— https://github.com/bropines/tailsocks/releases/tag/v4.0.0 (2026-09-07)

**Subnet-router footgun (Synology/NAS):** `--accept-routes=false` is mandatory
on a router, or Tailscale's policy routing diverts the box's *own* LAN traffic
into the tailnet and it loses its LAN IP while still showing "online".
Break-glass (headless): reach it over its Tailscale IP and run `tailscale
down` — restores LAN immediately; do NOT power-cycle (boot re-applies the bad
state). **[C]**
— https://github.com/xiiisins/homelab/blob/HEAD/docs/known-issues/tailscale.md (2026-09-28)

---

## 4. DERP, NAT traversal, streaming latency

**See the actual path per peer:**
```bash
tailscale ping --c=10 --until-direct=false <peer>
# pong ... via 198.51.100.20:41641 in 18ms   # direct
# pong ... via DERP(par) in 42ms              # relayed
```
First packets often ride DERP while NAT traversal settles; `--until-direct=false`
keeps watching instead of stopping at the first direct pong. **`tailscale
netcheck`** reports NAT type + DERP latency. **[C]**
— https://github.com/vincent-hd/.nixfiles/blob/HEAD/docs/research-sunshine-tailscale.md (2026-10-01)

**DERP is TCP/443, rate-limited, shared.** Fine for control traffic; for
streaming it adds latency and a ceiling. All connections *start* on DERP then
upgrade to P2P when possible. For KaviTV-over-tailnet: verify the path is
direct (`tailscale ping` from the app's node to SETHS-PC); if stuck on DERP,
streaming still works but expect higher latency and possible quality loss.
**[O/C]** — Tailscale connection-types docs; NAT deep-dive at
https://github.com/kmrule/ai-expert-skills/blob/HEAD/tailscale-headscale-expert/SKILL.md (2026-09-26)

**Precedent:** Sunshine/Moonlight game streaming over Tailscale is a proven
homelab pattern — low-latency video over the tailnet works when the path is
direct. **[C]** — vincent-hd research above.

---

## 5. ACLs / grants

**App capabilities** (`--accept-app-caps` + grants `app` block) forward
`Tailscale-App-Capabilities: {"cap": [...]}` to backends — and unlike identity
headers, they're set for tagged callers too. **[C]** — usetemi/skills
expose-services.md.

**WhoIs-per-request auth** (bscott/rdc, a Rust remote-desktop server): resolve
caller identity from the socket via LocalAPI whois, match against grants,
attach capabilities (`view`/`input`/`clipboard`) to the request, audit-log
every decision. This is the reference pattern for an RVG-class tool done
right. **[C]** — https://github.com/bscott/rdc/blob/HEAD/docs/architecture.md

---

## 6. Headscale (self-hosted control plane)

**Put the control plane OUTSIDE the LAN.** Behind CGNAT, a Headscale server
inside the lab is the least reachable component holding the reachability job.
Run it on a small VPS with a public IP; use its embedded DERP as relay of last
resort. **[C]**
— https://medium.com/@vdaluz/self-hosted-vpn-on-a-homelab-behind-cgnat-with-headscale-and-tailscale-703cee427333 (2025-12-19)

**Docker + Tailscale boot-order gotcha:** containers start before `tailscaled`
brings up the VPN IP → Docker silently drops port bindings to the not-yet-
existing IP. Containers look healthy but aren't on the VPN IP. Fix: restart
containers after tailscaled (or bind 0.0.0.0). **[C]**
— https://github.com/jordanhoelscher/jarvis-homelab-ai/blob/HEAD/runbooks/HeadscaleVPNDown.md (2026-08-08)

**Known costs:** no Funnel, no HA/replication, new client features lag until
Headscale supports them, mobile apps hide the custom control-plane URL in a
debug menu. **[C]** — https://news.ycombinator.com/item?id=43563396

**Why bother:** the SaaS control plane persistently sees topology, device
names, ACLs, DERP metadata, and behavioral patterns (which device streams
Jellyfin at 22:00 for 90 min). **[C]**
— https://github.com/nicolaspogorzelski/homelab-server-architecture/blob/HEAD/docs/decisions/headscale-migration.md (2026-10-01)

**Dashboard:** tale/headplane web UI. **[C]** — HN thread above.

---

## 7. Android (Razr)

**TailSocks v4.0.0** (third-party client): per-app exclusions that work in
root mode too, "run as exit node" switch, and a LAN-access switch that opens
its SOCKS5/HTTP proxy + DNS to the LAN (0.0.0.0) so other devices can route
through the phone. **[C]** — https://github.com/bropines/tailsocks/releases/tag/v4.0.0

**Official per-app split tunneling is still a feature request**
(tailscale/tailscale#4971, #6912) — don't wait for it; TailSocks covers it.
**[C]** — https://github.com/tailscale/tailscale/issues/20653

---

## 8. Debugging & misc

- `tailscale status --active` during a stream shows the live path. **[O]**
- **Taildrop:** `tailscale file cp <file> <node>:` — node-to-node file push,
  no separate service. **[O]**
- **MagicDNS** gives every node a stable name; mDNS (`.local`) also works
  on-LAN. Prefer names over IPs everywhere — LAN IPs drift invisibly.
  **[C]** — https://github.com/pironex9/homelab/blob/HEAD/docs/k3s/05_Wake_on_LAN.md
- **Mullvad exit nodes** exist as a Tailscale add-on for privacy-VPN egress.
  **[O]** (well-known product feature)
