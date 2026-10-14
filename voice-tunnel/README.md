# KaviBOT voice reverse-tunnel (PC side)

Private, tailnet-only path for the iPhone voice page to reach the KaviBOT
API on the VM: iPhone -> PC Tailscale Serve (https :8443) -> voice-relay.py
(127.0.0.1:8092) -> VM poller (outbound long-poll) -> KaviBOT API :8091.

The relay is stdlib-only Python, loopback-bound, and holds no secrets: the
KaviBOT API's bearer auth is enforced end-to-end by the API itself.

## Install (one paste, elevated PowerShell on SETHS-PC)

The exact one-paste snippet (pinned to a commit SHA) is delivered via ntfy
when a new version is published. It downloads the three files below from
jsDelivr (pinned, immutable) and runs the installer, which:

1. checks admin / Python / Tailscale,
2. installs to C:\AI\voice-relay\,
3. creates the KaviVoiceRelay scheduled task (SYSTEM, at startup, auto-restart),
4. health-checks the relay, then `tailscale serve --bg --https=8443` -> relay,
5. prints a plain-language scoreboard.

iPhone URL: https://seths-pc.tail1cffd9.ts.net:8443/v1/voice/

## Rollback

Elevated PowerShell: `powershell -File C:\AI\voice-relay\rollback-voice-relay.ps1`
Removes only the :8443 serve mapping (other serve entries untouched), stops
and unregisters the scheduled task, kills the relay. Port 8899 is never
touched by install or rollback.

## Files

- voice-relay.py -- the relay (stdlib only)
- install-voice-relay.ps1 -- one-paste installer
- rollback-voice-relay.ps1 -- clean removal
