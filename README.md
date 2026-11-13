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
