# Vega OS CI/CD Pipeline — Savant Research (2026-10-05)

How to turn a git push into a tested `.vpkg` with zero manual steps, and where
automation provably stops.

## Recommended pipeline design

Three jobs, in order, each gating the next:

```
quality  →  vpkg  →  release (tags only)
```

- **quality**: lint, types, unit tests, icon-band check, metadata check.
  Fast (<5 min). Fails the run before any expensive build.
- **vpkg**: install Vega SDK → build ARMv7 Release → `vpt validate` (must be
  0 errors) → size sanity check → upload artifact. The only job that needs
  the SDK.
- **release**: on `v*` tags only. Re-runs checks, verifies tag matches
  package version, downloads the CI-built artifact, verifies SHA-256,
  publishes a GitHub prerelease with checksums + SBOM.

This mirrors `looizao/jellyfin-vega-tailnet`'s proven CI [C], minus their
Go/browser-test stages which Seth's apps don't need.

## Workflow sketch

```yaml
name: Vega CI
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  VEGA_SDK_VERSION: 0.24.12112   # pin it; renovate/dependabot can't see this
  NODE_VERSION: "22.22.0"

jobs:
  quality:
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: npm
      - run: npm ci --ignore-scripts
      - run: npm run lint && npm run typecheck
      - name: Icon band check (launcher crops to 3:2)
        run: python3 scripts/check-icon-band.py assets/image/icon.png
      - name: Manifest sanity
        run: |
          grep -q 'com.amazon.category.main' manifest.toml
          grep -q '^build_number = [1-9]' manifest.toml

  vpkg:
    needs: quality
    runs-on: ubuntu-22.04
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: npm
      - name: Install Vega SDK
        run: |
          curl -fsSL https://sdk-installer.vega.labcollab.net/get_vvm.sh \
            -o "$RUNNER_TEMP/get_vvm.sh"
          # Pin: verify installer checksum (update when SDK changes) [C]
          echo "<sha256-of-installer>  $RUNNER_TEMP/get_vvm.sh" | sha256sum -c -
          NONINTERACTIVE=true SKIP_VEGA_INSTALL=true \
            VEGA_SDK_VERSION=${{ env.VEGA_SDK_VERSION }} \
            bash "$RUNNER_TEMP/get_vvm.sh"
      - name: Auto-bump build number
        env:
          BUILD_NUMBER: ${{ github.run_number }}
        run: |
          # github.run_number is monotonic per repo — perfect build_number [C]
          sed -i "s/^build_number = .*/build_number = $BUILD_NUMBER/" manifest.toml
          grep '^build_number' manifest.toml
      - name: Build ARMv7 Release
        run: |
          source ~/vega/env
          npm ci --ignore-scripts
          # Vega tools break on spaces in path — build in a clean copy [C]
          W="$RUNNER_TEMP/build-clean"
          rm -rf "$W" && cp -r . "$W"
          (cd "$W" && npx react-native build-vega \
            --target armv7 --buildType Release \
            --build-number ${{ github.run_number }})
          echo "VPKG=$(ls $W/build/armv7-release/*.vpkg | head -1)" >> $GITHUB_ENV
      - name: Validate
        run: |
          source ~/vega/env
          vega exec vpt validate "$VPKG"
          # Size sanity: real app is 100KB+; ~5KB = manifest-only, broken [C]
          test $(stat -c%s "$VPKG") -gt 100000
      - uses: actions/upload-artifact@v4
        with:
          name: app-armv7-${{ github.sha }}
          path: ${{ env.VPKG }}
          retention-days: 30

  release:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: vpkg
    runs-on: ubuntu-22.04
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Tag matches package version
        run: test "${{ github.ref_name }}" = "v$(node -p 'require("./package.json").version')"
      - uses: actions/download-artifact@v4
        with:
          name: app-armv7-${{ github.sha }}
          path: dist
      - run: (cd dist && sha256sum * > SHA256SUMS && sha256sum -c SHA256SUMS)
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/*
          prerelease: true
          generate_release_notes: true
```

## Key patterns (sourced)

1. **SDK install in CI** [C — Schnielz87/PowerIPTV `.github/workflows/build-apk.yml`,
   job `firetv-vega`, 2026]: `curl` the `get_vvm.sh` installer from
   `https://sdk-installer.vega.labcollab.net/get_vvm.sh`, run with
   `NONINTERACTIVE=true SKIP_VEGA_INSTALL=true VEGA_SDK_VERSION=<pin>`,
   then `source ~/vega/env`. Pin the SDK version in `env:` — CI breaks
   silently on SDK drift.
2. **Verify the installer checksum** [C — looizao/jellyfin-vega-tailnet
   `scripts/install-vega-sdk.sh`]: `sha256sum` the downloaded installer
   against a pinned hash before executing. Supply-chain hygiene for a
   binary that runs as the CI user.
3. **Docker builder alternative** [C — jellyfin-vega-tailnet
   `tooling/Dockerfile`]: multi-stage `ubuntu:22.04` + `node:22.22.0` +
   `golang:1.26.8`, installs SDK at image build time, `CMD` runs
   `source /root/vega/env && npm ci --ignore-scripts && npm run build:release`.
   In CI: `docker build -f tooling/Dockerfile -t builder:ci .` then
   `docker run --rm -e BUILD_NUMBER -v "$PWD:/work" builder:ci`.
   Tradeoff: reproducible, but the container writes outputs as **root**
   (ownership friction); native install on `ubuntu-22.04` avoids it.
4. **Caching** [C — jellyfin-vega-tailnet `ci.yml`]: `actions/setup-node`
   with `cache: npm` (biggest win — node_modules). SDK itself is NOT
   cached by any project found — the install is ~2–4 min, acceptable per
   run; caching `~/vega` via `actions/cache` is untested and risks stale
   toolchains. Don't.
5. **Build-number auto-bump** [C — PowerIPTV]: `github.run_number` is
   monotonic per repository — `sed -i "s/^build_number = .*/build_number =
   $BUILD_NUMBER/" manifest.toml`. Never 0, always increasing, zero
   bookkeeping. (Multi-app monorepo: use per-app offsets or separate
   workflows.)
6. **`vpt validate` in CI** [C — PowerIPTV, jellyfin-vega-tailnet]:
   `vega exec vpt validate "$VPKG"` — exit non-zero on any error, so it
   gates the artifact upload directly. Follow with the size sanity check
   (`>100000` bytes); a ~5KB vpkg is manifest-only and broken.
7. **No spaces in build path** [C — PowerIPTV, German comment in workflow]:
   "Die Vega-Werkzeuge vertragen keine Leerzeichen im Pfad" — Vega tools
   break on spaces in the path. Build in a clean copy under `$RUNNER_TEMP`.
8. **`npm install --ignore-scripts`** [C — jellyfin-vega-tailnet, PowerIPTV]:
   both projects use it. Vega's native modules come from the SDK, not
   npm lifecycle scripts; `--ignore-scripts` avoids hostile/slow postinstalls.
9. **Icon-band check in CI** [C — fortemate/dicechess-tv
   `native/test/splash.test.ts`, 2026-09-23]: the launcher crops icons to
   3:2, only y=100–412 of 512 survives. Their test fails the build if
   artwork leaves the band. Seth's `scripts/check-icon-band.py` (PIL port,
   used by the Seth Launcher build) is the drop-in equivalent —
   `python3 scripts/check-icon-band.py assets/image/icon.png` in the
   quality job.
10. **Pinned action SHAs** [C — jellyfin-vega-tailnet]: they pin
    `actions/checkout@3d3c42e5...` etc. by SHA with version comments.
    Worth copying for supply-chain safety on a pipeline that ships to a TV.

## What stays manual and why

- **LAT upload: no automation exists.** The App Submission API cannot manage
  Live App Testing, cannot do first-version submissions, and treats VPKG
  as unsupported [O — Amazon docs, verified in the amazon-appstore skill
  research 2026-10-05]. The `galonga/upload-amazon-appstore` GitHub Action
  is **APK-only** (`apkFile:` input, `.apk` in the README) and requires the
  app to already be live [C — galonga/upload-amazon-appstore README].
  There is no VPKG equivalent and no console-API workaround short of
  automating the browser against Amazon's ToS — don't.
- **The closest to hands-free:** CI builds → validates → publishes a GitHub
  prerelease with the `.vpkg` + SHA-256. A human then does the 5-minute
  console step: LAT → upload VPKG → add tester → submit. Keep a
  `docs/lat-upload-checklist.md` in each app repo so the manual step is
  mechanical, not remembered.
- **Device testing can't run in CI.** No cloud Vega devices; the Virtual
  Device is x86_64-only and doesn't exercise the ARMv7 media path. The
  pipeline proves the package is *valid*, not that it *plays*. Keep the
  on-stick deploy loop (socat + vda) as the human verification step.
- **First-ever Appstore submission** is console-only by Amazon's design —
  plan the pipeline around LAT from day one.

## Recommendation for Seth's apps

One reusable workflow (`.github/workflows/vega.yml`) templated per app repo
(or per app dir with path filters, like digipal-players' `ci-workflows/`
pattern [C — aysikder-oss/digipal-players README]). Per-app pins:
`VEGA_SDK_VERSION`, manifest path, package name. Shared: quality gates,
icon check, SDK install, build-number from `github.run_number`,
`vpt validate` + size gate, artifact → prerelease. Manual: LAT upload via
checklist. When the KaviTV rebuild proves the loop, copy it to the other
15 apps.
