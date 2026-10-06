# Credential / Access Inventory

**Status:** Template created 2026-10-05. **Rule:** this inventory records the
EXISTENCE and SCOPE of access — never secret values. No passwords, API keys,
tokens, cookies, private keys, or session secrets appear here, in any draft
of this file, or in any commit.

**Target repo location:** `kellner-dot/seth-dashboard/kavi-team/CREDENTIAL-INVENTORY.md`.

## How to use

Each row names a credential/access, what it unlocks, where the value lives
(never the value), who may use it, and its rotation state. If a value is
unknown, the row says "location unknown — needs Seth," not a guess.

| Access | Unlocks | Stored at (location only) | Usable by | Rotation / notes |
|--------|---------|---------------------------|-----------|------------------|
| Emby admin API key | Full Emby admin API | Seth's keeping; no copy on file (Emby API returns 401 without it) | Seth | Needed for Layer 3 test-user creation OR Seth creates user via Dashboard |
| Emby test user (planned) | KaviTV 3 channels only, non-admin | OS credential store / Secure Vault on PC (to be created) | Sentinel Layer 3 tester | Create once; rotate on Seth's decision or suspected exposure |
| RVG X-RVD-Token | RVG agent API on PC | Drive (re-download per session to /dev/shm, 0600) | Kavi team per standing auth | Re-download each session; /dev/shm wipes on VM replacement |
| GitHub App `meta-muse-ai` | kellner-dot repos (contents/issues/PRs; NO Actions/Admin/Secrets) | GitHub App installation | Kavi 4 | Permission expansion requested 2026-10-05 |
| TeraBox session | T: cloud mount (Facebook login) | PC app session | Seth | Re-auth needs Seth's click (known SPOF) |
| Tailscale | Tailnet membership | Control plane + node keys | Seth (admin console) | Machine key: leave as-is per Seth |
| Gmail OAuth (kavi-mail) | kavi-mail label read/write | Connector | Kavi 4 | Standing |
| Drive OAuth | Emergency docs, kavi-history | Connector | Kavi 4 | Standing |
| Chelsea Emby user | 605 non-adult channels allowlist | Emby user DB | Chelsea | Adult channels excluded by allowlist |
| MeshCentral | (credential file flagged for rotation 09-27) | `~/workspace/user/files/meshcentral-credentials.txt` — ROTATE AND DELETE | Seth | Hygiene item from 09-27, still open |

## Audit rules

- Quarterly (or on incident): confirm each row still accurate; confirm no
  secret values leaked into the file (`grep -i 'password\|token\|secret\|key='`).
- Any new credential created for Kavi work gets a row here within 24h —
  location and scope, never the value.
- kavi-mail never carries credentials. Ever.
