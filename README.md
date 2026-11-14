# ofGLMatrix

A cross-platform openFrameworks graphics compatibility and regression test.
It combines a familiar graphicsExample scene with automated checks and an
on-screen results panel, helping reproduce rendering failures across desktop
OpenGL, OpenGL ES, and WebGL.

## Core checks

- Requested context and selected OF renderer/version.
- Texture upload, offscreen framebuffer drawing, and pixel readback.
- Shader compilation, linking, drawing, and expected output colour.
- Indexed VBO rendering and instancing when supported by the context.
- Tessellated paths, including index validity and a visible star-arm check for
  16-bit/32-bit index mismatches.
- Screen readback of the graphicsExample scene and GL error checks.
- Compute shader/SSBO output on eligible Android ES 3.1+ builds.

Results are reported as `PASS`, `FAIL`, or `n/a` on screen and in logs. A final
`GL_MATRIX ... RESULT=PASS|FAIL` line includes context, renderer, device, and
individual check results. These are targeted smoke/regression checks, not a
complete rendering conformance suite.

## Layout

| Directory | Purpose |
| --- | --- |
| `shared/` | Desktop/Web test core and rendering smoke test |
| `glMatrixDesktop/` | Desktop GL application |
| `glMatrixWeb/` | Emscripten/WebGL application and optional capture runner |
| `glMatrixIOS/` | iOS application and platform-local test headers |
| `glMatrixAndroid/` | Android application, platform-local test headers, and APK variant builder |

The platform-local headers are retained from the original test applications;
changes to shared checks should also be reviewed in those copies.

## Setup

This repository contains application/test sources, not openFrameworks or its
platform dependencies. Clone it into an existing, configured OF checkout:

```text
openFrameworks/
  addons/
  libs/
  apps/
    ofGLMatrix/
      shared/
      glMatrixDesktop/
      glMatrixWeb/
      glMatrixIOS/
      glMatrixAndroid/
```

The project files assume this directory depth. Use an OF version providing the
APIs used here, including Android GLES minor-version selection, and install its
normal platform dependencies and toolchains.

### Desktop

Build from `glMatrixDesktop` using the OF makefiles (`make Release`). Run the
built executable with `OF_GL_VERSION=2.1`, `3.2`, `3.3`, or `4.1` to select a
context; the default is `3.2`. Context availability depends on the driver.

The app finishes after its initial test frames and exits with status 0 for a
pass or 1 for a failure. Set `OF_KEEP=1` to keep the window open. Optional
`OF_SHOT=/absolute/path.png` saves a screenshot.

### Web

Build `glMatrixWeb` with the configured OF Emscripten toolchain and serve the
resulting `bin/em/glMatrixWeb/` directory over HTTP. The result is also written
to the page title for automation. WebGL 2 is the default. `?webgl=1` labels a
WebGL 1 run; the browser must also disable WebGL 2 so OF takes its fallback path.

`cdp-shot.mjs` is an optional macOS Chrome capture runner. It requires a Node.js
version with global `fetch` and `WebSocket`, and Chrome at its standard macOS
installation path:

```sh
node cdp-shot.mjs <url> <screenshot.png> <results.log> [--disable-webgl2]
```

### iOS

Open `glMatrixIOS/glRenderSmokeTest.xcodeproj` and run the
`glRenderSmokeTest` scheme. Select `OF_GLES=1`, `2`, or `3` in the launch
environment; the default is `2`. For simulator launches, pass
`SIMCTL_CHILD_OF_GLES` through `xcrun simctl launch`. Available versions depend
on the device/simulator. Configure your own signing team for device builds.

### Android

Open `glMatrixAndroid` in Android Studio, configure the SDK locally, and install
the SDK/NDK versions specified in `ofApp/build.gradle`. The current project
targets `arm64-v8a`. Build the debug APK with `./gradlew assembleDebug`.
Results are displayed on screen and emitted with the logcat tag `GLMATRIX`.

The default request is ES 3.2. On devices permitting developer properties,
`adb shell setprop debug.of.gles 3.0` overrides the request for the next launch.
`build-variants.sh` builds separate APKs for ES 1.1, 2.0, 3.0, 3.1, and 3.2,
so device farms can select a version without setting properties. The script
uses macOS/BSD `sed` and updates the variant header, application ID, and label.
Set `JAVA_HOME` and `ANDROID_HOME` for your machine as needed.

Generated builds, logs, captures, SDK paths, and local signing settings are
excluded from version control.

## Continuous integration

[Graphics against OF master](../../actions/workflows/graphics.yml) runs on pushes,
pull requests, manual dispatch, and weekly. Every matrix job checks out the same
resolved commit of `openframeworks/openFrameworks` **master**, builds OF from
source, and uses upstream's dependency downloads. The OF commit SHA is recorded
in the job summary and artifacts.

| Job | Coverage |
| --- | --- |
| Linux desktop | GL 2.1, 3.2, 3.3, 4.1; Mesa software rendering under Xvfb |
| macOS desktop | Build only; hosted VM cannot create an OpenGL context |
| WebGL 1 / WebGL 2 | Separate headless Chrome runs using SwiftShader; WebGL 1 forces browser fallback |
| iOS | Simulator runs for ES 1.1, 2.0, 3.0 |
| Android arm64 | Build and package an arm64 APK |
| Android x86_64 | Emulator runs for ES 1.1, 2.0, 3.0, 3.1, 3.2 where advertised |

Each runtime case must produce the matching `GL_MATRIX ... RESULT=PASS`. Crashes,
timeouts, missing results, lower-version fallbacks, and failed pixel checks fail
the job. Android versions above the emulator's advertised GLES maximum are
explicitly reported as **SKIP**, with capable-device testing still required;
skips are never counted as passes. Emulator/software-renderer checks do not
replace testing on physical GPUs.

The WebGL 1 job uses a WebGL 2-capable binary with WebGL 2 disabled in Chrome,
as documented by the app, and verifies that the actual context is WebGL 1.
Upstream currently references ES3 framebuffer symbols even when built with its
`OF_WEBGL_VERSION=1` flag, so a WebGL-1-only link fails. CI does not patch OF to
work around that separate build issue. The CI HTTP server supplies COOP/COEP
headers required by upstream's Emscripten pthreads build.

On a Mac with OpenGL support, `python3 ci/run.py desktop` runs all four desktop
versions after building the app. The hosted macOS job reports build coverage
explicitly instead of treating its missing graphics device as a rendering pass.

Each job presents build and runtime status in tables, with one row per API and
concise failure reasons. The final `Graphics result` job combines the whole
matrix into a single table; full diagnostics remain collapsed below each job
summary. Infrastructure errors (such as simulator boot migration timeouts) are
shown separately from rendering failures, and unexecuted APIs are marked
`NOT RUN`. Artifact upload/download actions use Node.js 24.

iOS simulator startup begins before compilation so initial data migration can
run in parallel. The test runner waits up to 15 minutes for boot and saves a
separate `simulator-boot.log` if startup fails.

Build logs, runtime logs, screenshots, result JSON, and APKs are uploaded as
short-lived Actions artifacts and stay out of git. `Graphics result` is the
aggregate status suitable for branch protection.

For local Android builds, `-PofAbi=x86_64` selects the emulator ABI and
`-PofNdkVersion=<version>` overrides the NDK pin. The default ABI stays arm64.
