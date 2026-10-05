# Embedding Tailscale tsnet inside a Vega OS (.vpkg) app

Savant research, 2026-10-05. The linchpin for KaviTV's tailnet control endpoint.

## TL;DR

It works and there's exactly one public proof: `looizao/jellyfin-vega-tailnet`
(last commit 2026-09-13). Recipe: Go `tsnet.Server` compiled to a C archive
with cgo → linked into a KeplerScript C++ TurboModule → JS calls it via
promises. Cross-compiled for ARMv7 with Vega's own Clang. **No special
manifest privileges required** — tsnet runs inside the normal app sandbox.
The reference project only does *outbound* dialing; KaviTV's control endpoint
needs *inbound* `Listen`, which is standard tsnet API.

## 1. The reference implementation [C]

**Repo:** https://github.com/looizao/jellyfin-vega-tailnet (MIT, last commit 2026-09-13)
**What it does:** Jellyfin client for Vega; the stick joins the tailnet from
inside the app, then reaches the Jellyfin server over the tailnet. No Tailscale
daemon installed on the stick.
**Status honesty:** the repo calls itself a "device-testing preview" —
"Physical Fire TV playback, focus, key mapping, and lifecycle still require
validation" (`docs/TESTING.md`). ARMv7 release compilation and VPT validation
passed; no Appstore submission is claimed.

**GitHub-wide check:** repo search for "tailscale vega fire tv" returns nothing
else; `tsnet` code search surfaces only generic (non-Vega) projects. This is
the only public tsnet-in-Vega implementation. Bleeding edge, one data point.

## 2. Architecture: the four layers

```
JS (src/client.ts)
  → TurboModuleRegistry.getEnforcing('Tailscale')      # NativeTailscale.ts
  → C++ TurboModule (kepler/turbo-modules/Tailscale.cpp)
  → C ABI (native/bridge/main.go, //export)
  → Go engine (native/engine/engine.go → tsnet.Server)
```

### Layer 1 — JS API (`src/native/NativeTailscale.ts`) [C]

```ts
export interface Spec extends KeplerTurboModule {
  start(config: string): Promise<string>;
  status(): Promise<string>;
  stop(): Promise<boolean>;
  checkServer(): Promise<string>;
  engineVersion(): string;
}
```

Config is a JSON string `{serverUrl, hostname, authKey}`; all results are
JSON strings parsed by `client.ts`. `safeError()` redacts `tskey-…` from
any error text before it reaches logs/UI.

### Layer 2 — C++ TurboModule (`kepler/turbo-modules/Tailscale.cpp`) [C]

- Each call runs on a **detached `std::thread`** — never the JS thread.
- Data dir is hardcoded: `/home/app_user/packages/<package-id>/data`
  (Vega's app-private dir pattern; created 0700).
- **Auth-key hygiene:** after `jv_start`, the config string is zeroed in
  memory: `std::fill(config.begin(), config.end(), '\0')`.
- RAII `EngineOwner` — destructor calls `jv_stop()`: "the last native
  worker releases the engine owner and closes its streams."
- Spec is codegen'd, never hand-written:
  `npx keplerscript-turbomodule-api codegen src/native/NativeTailscale.ts
  --new --namespace jellyvega --className Tailscale`
  (`scripts/generate-turbomodule-spec.sh`; `--check` mode for CI).

### Layer 3 — C ABI (`native/bridge/main.go`) [C]

```go
//export jv_start
func jv_start(dir, config *C.char) *C.char   // JSON in → JSON snapshot out
//export jv_status
func jv_status() *C.char
//export jv_stop
func jv_stop()
//export jv_check
func jv_check() *C.char
```

Mutex-protected singleton. Caller owns returned C strings (must `free()`).

### Layer 4 — Go engine (`native/engine/engine.go`) [C]

```go
node := &tsnet.Server{
    Dir:      filepath.Join(e.dir, "tailscale"),
    Hostname: config.Hostname,
    AuthKey:  config.AuthKey,   // one-shot, memory-only
    Logf:     logger.Discard, UserLogf: logger.Discard,
}
node.Start()
```

- **Identity:** tsnet persists node identity in `<dir>/tailscale`.
  App settings (`serverUrl`, `hostname`) go in `settings.json` mode 0600;
  **`config.AuthKey = ""` before persisting** — enrollment keys never touch disk.
- **Idempotent start:** same server+hostname and no new auth key → returns
  current snapshot without restarting.
- Their gateway binds **loopback only** (`127.0.0.1:18765`) — the WebView
  talks to it; all tailnet traffic is *outbound* via `node.Dial`.
- **Egress guard:** `tailnetDial` resolves hosts only through Tailscale's
  authenticated network map (MagicDNS name or 100.x IP); public DNS, LAN,
  and proxy fallbacks are deliberately refused.
- Status via `node.LocalClient().Status(ctx)` → BackendState, AuthURL,
  Health, TailscaleIPs.

## 3. Build recipe: Go → ARMv7 → .vpkg [C]

`native/go.mod`: `tailscale.com v1.102.4`, Go 1.26.6.

**The critical file is `CMakeLists.txt`** (project root) — invoked by the
Vega RN build. It cross-compiles the Go bridge *for the target arch*:

```cmake
# arm/armv7 → GOARCH=arm GOARM=7 ; aarch64 → GOARCH=arm64 ; x86_64 → amd64
COMMAND "${CMAKE_COMMAND}" -E env
  "GOOS=linux" "GOARCH=${JELLYVEGA_GOARCH}" "GOARM=${JELLYVEGA_GOARM}"
  "CGO_ENABLED=1"
  "CC=${CMAKE_C_COMPILER}"                    # Vega's Vodka Clang, not host gcc!
  "CGO_CFLAGS=--sysroot=${CMAKE_SYSROOT} ... -marm"   # -marm: cgo's ARM asm bridge can't be Thumb
  "CGO_LDFLAGS=--sysroot=${CMAKE_SYSROOT} ..."
  go build -buildvcs=false -trimpath -buildmode=c-archive -ldflags=-buildid=
    -o libtailscale.a ./bridge
```

Then:

```cmake
kepler_add_turbo_module_library(jellyvega
  kepler/AutoLinkInit.cpp
  kepler/turbo-modules/generated/TailscaleSpec.cpp
  kepler/turbo-modules/Tailscale.cpp)
target_link_libraries(jellyvega PRIVATE libtailscale pthread dl m)
```

`react-native.config.js` tells the build where Kepler sources live:
`project.kepler.sourceDir: '.'`. Docker builder (`tooling/Dockerfile`):
node:22.22.0 + golang:1.26.8 + ubuntu:22.04, installs the Vega SDK.

**Build commands:**
```bash
npm run build:native-host   # host c-archive + smoke test (prebuilt/host/)
npx react-native build-vega --build-type Release --target armv7 \
  --build-version 0.1.1 --build-number N   # via scripts/build-vega.sh
```

## 4. What KaviTV needs beyond the reference: INBOUND listeners

The reference project only dials *out*. KaviTV's control endpoint
(`/status`, `/tune`, `/diag`) needs the app to *listen* on the tailnet.
Standard tsnet API [O]:

```go
// after node.Start():
ln, err := node.Listen("tcp", ":8080")          // tailnet-only listener
// or with free auto-TLS on the MagicDNS name:
ln, err := node.ListenTLS(":443")
lc, _ := node.LocalClient()
http.Serve(ln, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    who, err := lc.WhoIs(r.Context(), r.RemoteAddr)  // tokenless caller identity
    // who.UserProfile.LoginName, who.Node.ComputedName, who.Node.Tags
}))
```

Sources: `tailscale/tailscale` servetls example (`lc.GetCertificate` for TLS);
`loft-sh/tunnel` tsnet server example (`Listen` + `WhoIs` pattern).
Nothing in the Vega sandbox prevents this — a tsnet listener binds inside
tsnet's netstack, not a real device interface, so no `CAP_NET_BIND_SERVICE`
or manifest privilege is involved.

**Design for KaviTV:** add `jv_listen(port)` / extend the C ABI with
`jv_serve(config)` that starts an HTTP mux on `node.Listen`, with a
WhoIs middleware allowing only Seth's login (and/or his nodes' tags).
Keep the reference's outbound `tailnetDial` for the app calling *out*
to the relay if needed.

## 5. Identity, Dir, and the stale-state gotcha [C]

- tsnet's `Dir` (`<data>/tailscale`) holds node keys. A stale `Dir`
  silently keeps the old identity and ignores a new auth key — always set
  `Dir` explicitly; `TSNET_FORCE_LOGIN=1` forces re-auth.
- Reference pattern: one-shot auth key passed in `start()` config,
  zeroed in C++ after use, redacted from errors, never persisted.
- **Ephemeral nodes:** `tsnet.Server{Ephemeral: true}` + a short-lived
  (e.g. 5-minute, non-reusable or tagged) auth key = self-cleaning node;
  provision the key via the Tailscale Admin API at build/deploy time.
- Hostname validation in the reference (≤63 chars, lowercase alnum +
  internal hyphens) — reuse it; Tailscale rejects bad hostnames at
  enrollment.

## 6. Sandbox survival [C]

From `docs/ARCHITECTURE.md`: "The operating system controls WebView storage
and app process lifetime. **A killed process reconnects on the next launch;
background playback and continuous operation while other apps run are not
promised.**"

Consequences for KaviTV:
- Start tsnet lazily on app launch, not at install. Reconnect is cheap
  (identity persisted in `Dir`).
- Don't depend on the listener surviving backgrounding — the control
  endpoint is for "app is open" operation; use the Emby Sessions API
  workaround when the app is closed.
- `jv_stop()` on teardown; RAII owner pattern handles abandoned threads.

## 7. Memory footprint [P, reasoned]

The repo publishes no memory numbers. tsnet embeds userspace WireGuard
(`wireguard-go`) + netstack + the full Tailscale client: expect **~20–60 MB
RSS** for an idle-to-moderate node (community-observed range for tsnet
embeds). On the 1 GB 4K Select this is significant but workable *if*:
- tsnet starts only when the app is foregrounded,
- `Logf: logger.Discard` (reference does this — logging is a real cost),
- no debug/verbose envknobs in release builds.
Measure on-device with `vda shell` + `/proc` during the KaviTV build;
treat 100 MB as the red line.

## 8. Appstore review risk [P]

Signals, honestly labeled:
- **Good:** the manifest needs **zero** special privileges for tsnet —
  no `[needs.privilege]`, no network declarations. From the reviewer's
  chair it's just a native library doing TLS.
- **Good:** all traffic is encrypted Tailscale; the reference's egress
  guard (tailnet-only dialing) is a strong story for "what does this
  network code do".
- **Uncertain:** no public precedent for a tsnet-in-Vega Appstore
  submission (the reference project hasn't submitted). Amazon's review
  is a black box here.
- **Mitigation:** ship KaviTV through **Live App Testing** first (private,
  Seth-only) — full launcher integration with none of the public-review
  exposure. Promote to production only after LAT proves stable.
- The repo's own INSTALL.md: "A successful VPT build does not grant
  Appstore approval or bypass device enrollment."

## 9. Build checklist for KaviTV

1. Copy `native/` (bridge/engine), `kepler/` TurboModule pattern,
   `CMakeLists.txt` (adapt arch map + target names), `react-native.config.js`.
2. Write `NativeKaviTV.ts` spec → run the codegen script.
3. Extend the C ABI: `jv_serve(port)` starting the HTTP mux on
   `node.Listen`, WhoIs middleware, tailnet-only.
4. Endpoints: `GET /status`, `POST /tune`, `GET /diag` (+ shared-secret
   header as second factor).
5. Ephemeral node + 5-min auth key; `Dir` under the app data dir.
6. `vpt validate` = 0 errors; VPKG size sanity (Go adds MBs — expect
   several MB, not KB).
7. Deploy, reboot, verify tile; test `/status` from another tailnet node.
8. LAT submission for real launcher integration.

## Sources

- https://github.com/looizao/jellyfin-vega-tailnet (ARCHITECTURE.md,
  native/bridge/main.go, native/engine/engine.go,
  kepler/turbo-modules/Tailscale.cpp, CMakeLists.txt, docs/TESTING.md,
  docs/INSTALL.md) — accessed 2026-10-05, last commit 2026-09-13 [C]
- https://github.com/tailscale/tailscale/blob/main/client/tailscale/example/servetls/servetls.go — `lc.GetCertificate` TLS pattern [O]
- https://github.com/loft-sh/tunnel/blob/main/examples/tsnet/cmd/server/main.go — `Listen` + `WhoIs` pattern [O]
- GitHub repo search "tailscale vega fire tv" (2026-10-05): no other
  tsnet-in-Vega projects [C]
- tsnet memory estimate: reasoned from wireguard-go + netstack embed
  characteristics, no on-device measurement yet [P]
