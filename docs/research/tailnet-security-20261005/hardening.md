# Tailnet Security Hardening — 2026-10-05

Savant research on locking down Seth's Tailscale tailnet. Every finding is
labeled [O] verified-official / [C] verified-community / [P] plausible,
with source URL + date.

## 1. Threat model

Single-user tailnet (Seth only). Realistic threats, ranked:

1. **Stolen auth key** — a leaked reusable/pre-authorized key enrolls rogue
   nodes silently. Mitigated by: one-off ephemeral keys, Tailnet Lock,
   device approval, webhooks on `nodeCreated`.
2. **LAN-local attacker vs the stick** — port 5555 on 10.0.0.151 takes
   unauthenticated connections from ANY home-LAN device. Tailscale ACLs
   cannot see this traffic at all. Mitigated by: `vda pair` (device layer).
3. **Over-broad subnet route** — SETHS-PC advertises `10.0.0.0/24`, exposing
   the ENTIRE home LAN (router admin, printer, everything) to anyone the
   ACLs let through the route. Mitigated by: narrow ACLs on the route,
   consider shrinking the advertised CIDR.
4. **Accidental public exposure** — `tailscale funnel` publishes to the open
   internet with no auth. Mitigated by: never use funnel; serve only.
5. **Compromised node pivoting** — default allow-all policy lets any node
   reach any port. Mitigated by: explicit grants, least privilege.

## 2. Current exposure inventory (2026-10-05)

| Surface | Where | Who can reach it today |
|---|---|---|
| Stick ADB 5555 | 10.0.0.151 (LAN) | Anyone on home LAN (no auth) |
| Stick ADB 5555 | via subnet route | Anyone on tailnet (default allow-all) |
| KaviTV relay :8100 | SETHS-PC tailnet IP | Anyone on tailnet |
| XC bridge :8880 | SETHS-PC tailnet IP | Anyone on tailnet |
| Emby :8096 | SETHS-PC tailnet IP | Anyone on tailnet |
| Ops console :8890 | SETHS-PC tailnet IP | Anyone on tailnet |
| RVG | SETHS-PC | Anyone on tailnet (app-level auth) |
| Subnet 10.0.0.0/24 | via SETHS-PC | Anyone on tailnet |
| Future tsnet app nodes | ephemeral | Anyone on tailnet |

The default tailnet policy is **allow-all** — every row above is currently
open to every tailnet node. [O — tailsnitch ACL-001, tailscale.com]

## 3. Recommended policy (grants syntax)

Use `grants` for all new rules (Tailscale's recommended syntax; legacy
`acls` still work but get no new features). [O — tailscale/tailscale-skill]

```hujson
{
  // All tags owned by the admin only. Never autogroup:member or * —
  // whoever can mint a tag inherits everything that tag can reach.
  // [C — tailsnitch ACL-006, ACL-011]
  "tagOwners": {
    "tag:server":   ["autogroup:admin"],  // SETHS-PC
    "tag:app":      ["autogroup:admin"],  // ephemeral tsnet app nodes
    "tag:watchdog": ["autogroup:admin"],  // if the watchdog ever gets its own node
  },

  "grants": [
    // Seth's own devices → server ports, least privilege per port.
    // Replace sethryankellner@gmail.com with the real login email.
    {"src": ["sethryankellner@gmail.com"], "dst": ["tag:server"], "ip": ["tcp:8096"]},  // Emby
    {"src": ["sethryankellner@gmail.com"], "dst": ["tag:server"], "ip": ["tcp:8100"]},  // KaviTV relay
    {"src": ["sethryankellner@gmail.com"], "dst": ["tag:server"], "ip": ["tcp:8880"]},  // XC bridge
    {"src": ["sethryankellner@gmail.com"], "dst": ["tag:server"], "ip": ["tcp:8890"]},  // ops console

    // Stick ADB through the subnet route — ONLY Seth, ONLY port 5555.
    // This is the tailnet half of the 5555 lockdown (see §8).
    {"src": ["sethryankellner@gmail.com"], "dst": ["10.0.0.151"], "ip": ["tcp:5555"]},

    // Ephemeral app tsnet nodes → only what they need. Example: KaviTV
    // app node needs nothing inbound from others; it only serves its
    // own control endpoint to Seth's devices (covered above by direction).
    // Deny-by-default means no rule = no access. Add per-app rules here
    // as apps ship, one port at a time.
  ],

  // Route auto-approval: ONLY the tagged server may have its routes
  // auto-approved. Never autogroup:member or * here — that lets any
  // compromised node advertise routes and hijack traffic.
  // [C — tailsnitch ACL-005]
  "autoApprovers": {
    "routes": {
      "10.0.0.0/24": ["tag:server"],
    },
  },

  // Policy tests: they run on every save and fail loudly on regressions.
  // Always test denials, not just allows. [C — tailsnitch ACL-003]
  "tests": [
    {
      "src":    "sethryankellner@gmail.com",
      "accept": ["tag:server:8096", "tag:server:8100", "10.0.0.151:5555"],
      "deny":   ["tag:server:22"],
    },
  ],
}
```

Notes:
- Grants are **unidirectional** (src → dst); return traffic is implicit
  (stateful). There is no "deny" — absence of a grant is denial. [O]
- `*` as a destination now resolves to the CGNAT range (100.64.0.0/10),
  not 0.0.0.0/0 — write explicit CIDRs for subnets. [C]
- Tag SETHS-PC as `tag:server` in the admin console (Machines → Edit tags).
- tsnet app nodes join with `--advertise-tags=tag:app` on a 5-minute
  ephemeral auth key (see §5).

## 4. Subnet-router hygiene

- The route `10.0.0.0/24` is a **trust boundary**: traffic past the router
  to LAN destinations is unencrypted on the LAN segment, and the ACLs are
  the only filter. [C — tailsnitch NET-003]
- Keep manual approval (don't auto-approve) OR use the tag-scoped
  autoApprovers above — never `*`/`autogroup:member`. [C — ACL-005]
- Consider narrowing: if only the stick needs reaching, `10.0.0.151/32`
  advertises just the stick instead of the whole LAN. Trade-off: future
  LAN devices (printer, etc.) need route changes.
- Document why the route exists and who may use it (the grant in §3).

## 5. Key hygiene

- **Prefer one-off, ephemeral, short-expiry keys.** Reusable keys can enroll
  unlimited nodes if stolen (HIGH). >90-day expiry is flagged. [C — AUTH-001, AUTH-002]
- The tsnet 5-minute ephemeral pattern is exactly right: key mints one
  tagged node, node auto-removed when gone. Generate via Tailscale API.
- **Tagged devices get key expiry DISABLED by default** — indefinite access
  if compromised. Review and re-enable expiry for long-lived infra tags.
  [C — DEV-001]
- Never put a reusable key in a repo, chat, or log. The Drive-transient
  flow is the right pattern.
- Rotate: delete keys you don't recognize in Admin → Settings → Keys;
  rotate every 90 days per community practice.

## 6. Device hardening

- **Device approval**: enable "require approval for new devices" so nothing
  joins silently — unknown joins show as pending for review. [C — DEV-009]
- **Tailnet Lock**: even with a stolen auth key, an attacker can't enroll
  rogue nodes without a trusted signing key. HIGH severity if off.
  Enable with `tailscale lock init` on a trusted node + a second signing
  key. For a single-user tailnet this is cheap and very effective.
  [C — DEV-010]
- **Key expiry on user devices**: phones/laptops should re-auth periodically
  (90d); don't disable expiry without reason. [C — DEV-008, DEV-013]
- **Client updates**: keep nodes within one release of stable (auto-update
  where available). [C — DEV-003]
- **Prune stale nodes**: remove devices not seen in 60+ days. [C — DEV-004]

## 7. Serve vs Funnel — the hard rule

- `tailscale serve` = **tailnet only**, Tailscale-identity authenticated.
- `tailscale funnel` = **public internet**, no authentication.
- Community consensus as a binding rule: **serve, never funnel**.
  [C — multiple fleet SKILLs, 2026]
- The ops console on :8890 is correctly tailnet-only today; keep it that
  way. If it ever needs serve-style HTTPS, use `tailscale serve` on
  SETHS-PC (this VM's Tailscale is a stub and can't serve).
- Layered pattern that survives mistakes: bind the service to loopback,
  expose via serve (tailnet-only), restrict via ACLs, app-level secret on
  top. The loopback bind is the layer that survives a later ACL mistake.
  [C — crickertech/nife]

## 8. The stick's 5555: vda pair vs tailnet ACLs — which layer?

**Both. They guard different surfaces.**

| Layer | What it protects | What it can't see |
|---|---|---|
| Tailnet ACLs (§3) | Which *tailnet nodes* can reach 10.0.0.151:5555 *through the subnet route* | Anything on the home LAN directly — ACLs only filter tailnet traffic |
| `vda pair` | The ADB handshake itself — requires pairing proof before any ADB session, **including from LAN-local attackers** | Nothing — it's device-level |

The stick's 5555 currently accepts **unauthenticated connections from any
home-LAN device** — no tailnet policy can fix that, because that traffic
never traverses Tailscale. `vda pair HOST [CODE]` (exists in VDA 2.6)
is the correct fix for the LAN surface; the §3 grant is the correct fix
for the tailnet-routed surface. Defense in depth: do the ACL grant now
(5 minutes, reversible), schedule the `vda pair` lockdown next (needs
testing — its exact Vega behavior is [P]).

## 9. Audit logging & monitoring

- **Config audit log**: 90-day retention, all plans. Shows policy changes,
  device adds/removals, key events. Check Admin → Logs. [O — tailscale.com]
- **Network flow logs**: 30-day, Premium/Enterprise only — not on the free
  plan. [O]
- **Webhooks**: subscribe to `nodeCreated`, `nodeDeleted`, `nodeApproved`,
  `nodeNeedsApproval`, `policyUpdate`, `userRoleUpdated` — this is how you
  hear about rogue joins. Could feed the watchdog as a future enhancement.
  [C — LOG-012]
- **Security contact email**: set it in General Settings so Tailscale's
  bulletins reach you. [C — LOG-011]
- Failed logins are visible only via your identity provider, not Tailscale.
  [C — LOG-004]

## 10. Hardening checklist (tailored from tailsnitch's 57 checks)

- [ ] Replace default allow-all with the §3 grants policy
- [ ] tagOwners restricted to autogroup:admin (all tags)
- [ ] autoApprovers scoped to tag:server (never * / member)
- [ ] Policy tests with accept AND deny assertions
- [ ] Device approval enabled for new joins
- [ ] Tailnet Lock initialized (+ second signing key)
- [ ] No reusable auth keys lying around; tsnet keys 5-min ephemeral
- [ ] Tagged devices: key expiry re-enabled where long-lived
- [ ] §3 grant for 10.0.0.151:5555 (tailnet half of stick lockdown)
- [ ] `vda pair` lockdown tested on the stick (LAN half)
- [ ] Serve-only rule; no funnel anywhere (verify: `tailscale serve status`)
- [ ] Webhooks on nodeCreated/policyUpdate (or calendar reminder to review)
- [ ] Security contact email set and verified
- [ ] Stale devices (>60d unseen) pruned
- [ ] MagicDNS names contain nothing sensitive (they hit CT logs if HTTPS on)
- [ ] Taildrop reviewed (default on = easy file exfil between nodes)

## Sources

- Official docs (via tailsnitch doc links, 2026): tailscale.com — ACL samples,
  policy syntax, tags, grants, auth keys, Tailnet Lock, key expiry, subnets,
  serve, funnel, audit logging, network flow logs, security hardening
  [O]
- tailsnitch (Adversis/tailsnitch, GitHub, 2026-10) — 57-check security
  reference: https://github.com/adversis/tailsnitch/blob/HEAD/docs/CHECKS.md
  [C]
- tailscale/tailscale-skill — ACL→grant conversion:
  https://github.com/tailscale/tailscale-skill/blob/HEAD/skills/tailscale/references/access-control.md
  [C]
- tankpkg/packages tailscale-expert — policy file reference:
  https://github.com/tankpkg/packages/blob/HEAD/skills/tailscale-expert/references/access-control.md
  [C]
- learn-skills.dev tailscale-policy-manager — autoApprovers, tests:
  https://github.com/neversight/learn-skills.dev/blob/HEAD/data/skills-md/trtmn/agent-skills/tailscale-policy-manager/SKILL.md
  [C]
- crickertech/nife — layered exposure pattern (loopback + serve + ACL + key):
  https://github.com/crickertech/nife/commit/b779ea11fca552bda4bbf24b140d6ddf4140af08
  [C]
- Community fleet SKILLs — "serve, never funnel" hard rule (2026) [C]
- mortennordbye/homelab — subnet-router-as-code with tag-scoped autoApprovers:
  https://github.com/mortennordbye/homelab/blob/HEAD/terraform/proxmox/hyper-cluster/tailscale/README.md
  [C]
