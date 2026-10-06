# Security — Credential and Access Requirements

## Standing rules (Seth's words, in force)

- "Do not expose, print, copy, or hard-code passwords, OAuth secrets, PATs,
  RVG tokens, private keys, or other credentials."
- "Do not create new credentials unless I explicitly authorize it."

## Test-user credential lifecycle (Layer 3)

1. **Creation:** Seth creates the dedicated Emby test user via Dashboard, or
   authorizes creation with an admin API key he provides via Secure Vault.
   The password is his choice or a generated one he approves.
2. **Storage:** OS credential store / Secure Vault on Seth's PC only. One
   copy. Never in the repository, source code, logs, diagnostics,
   documentation, chat, kavi-mail, or screenshots.
3. **Runtime use:** read into memory at test start; used for the Emby auth
   call; session token kept in memory for the run; both discarded when the
   run ends. Never written to disk.
4. **Logging:** authentication is logged as `auth: ok/failed` — never the
   password, never the token, never the Authorization header
   ([07](07-diagnostics-evidence.md)).
5. **Rotation:** on Seth's decision or any suspected exposure. Rotation is a
   human action, not an automated one.

## Least privilege

- The test user is non-admin, KaviTV-channels-only, minimum permissions
  ([05](05-emby-integration.md)). If Emby cannot restrict it that tightly,
  Layer 3 stays BLOCKED — security is not traded for test coverage.
- Sentinel scripts run as SYSTEM scheduled tasks with no interactive logon
  and no network credentials beyond what the OS store provides at runtime.
- The Sentinel never requests, handles, or stores Seth's admin credentials.

## No-secret auditing

- `sentinel-results.json`, dashboard HTML, logs, and digest content are
  auditable by inspection: `grep` for `password|token|secret|cookie|Authorization`
  must return nothing.
- Any diagnostic that would be more useful with a secret gets a better
  non-secret diagnostic instead (timings, counters, state names).

## Boundaries the Sentinel does not cross

- No auth/ACL bypass (Emby or otherwise).
- No Tailscale ACL, tag, or permission changes.
- No firewall or network changes.
- No credential creation beyond the single authorized test user.
- No destructive or irreversible action without Seth's explicit approval
  ([09](09-recovery-runbook.md)).
