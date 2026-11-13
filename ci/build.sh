#!/usr/bin/env bash
set -euo pipefail

: "${OF_ROOT:?}" "${APP_ROOT:?}" "${CI_PLATFORM:?}"
jobs=${NUM_CORES:-2}
python3 -m unittest discover -s "$APP_ROOT/ci" -p 'test_*.py'
cd "$OF_ROOT"

case "$CI_PLATFORM" in
  linux)
    sudo bash scripts/linux/ubuntu/install_dependencies.sh -y
    sudo apt-get install -y xvfb xauth libgl1-mesa-dri mesa-utils
    bash scripts/linux/download_libs.sh -t latest -a 64 -g 10
    make -C "$APP_ROOT/glMatrixDesktop" -j"$jobs" Release
    ;;
  macos)
    bash scripts/macos/download_libs.sh -t latest
    make -C "$APP_ROOT/glMatrixDesktop" -j"$jobs" Release
    ;;
  web)
    bash scripts/emscripten/download_libs.sh -t latest
    # Match the SDK pin maintained by upstream master, rather than a system emcc.
    version=$(sed -n 's/^VERSION=//p' scripts/emscripten/install_emscripten.sh)
    [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
    docker run --rm -v "$OF_ROOT:/src" -w /src \
      "emscripten/emsdk:$version" bash -euc '
        # OF master references ES3 FBO symbols even on its WebGL1 path.
        # Link a WebGL2-capable binary, then force WebGL1 in the browser.
        emmake make -C apps/ofGLMatrix/glMatrixWeb -j2 Release
      '
    ;;
  ios)
    bash scripts/macos/download_libs.sh -t latest
    xcodebuild -project "$APP_ROOT/glMatrixIOS/glRenderSmokeTest.xcodeproj" \
      -scheme glRenderSmokeTest -configuration Release -sdk iphonesimulator \
      -destination 'generic/platform=iOS Simulator' ARCHS="$(uname -m)" \
      CODE_SIGNING_ALLOWED=NO \
      CONFIGURATION_BUILD_DIR="$APP_ROOT/artifacts/ios-app" build
    ;;
  android)
    : "${ABI:?}" "${NDK:?}"
    "${ANDROID_HOME:?}/cmdline-tools/latest/bin/sdkmanager" \
      "ndk;$NDK" 'platforms;android-34' 'build-tools;37.0.0' 'cmake;3.22.1'
    bash scripts/android/download_libs.sh -t latest
    bash libs/openFrameworksCompiled/project/android/cmake.sh "$ABI"
    cd "$APP_ROOT/glMatrixAndroid"
    ./gradlew assembleDebug -PofAbi="$ABI" -PofNdkVersion="$NDK" --stacktrace --no-daemon
    apk=$(find ofApp/build/outputs/apk -name '*.apk' -type f -print -quit)
    test -n "$apk"
    unzip -l "$apk" | grep "lib/$ABI/libofApp.so"
    cp "$apk" "$APP_ROOT/artifacts/glMatrix-$ABI.apk"
    ;;
  *) echo "Unknown platform: $CI_PLATFORM" >&2; exit 1 ;;
esac
