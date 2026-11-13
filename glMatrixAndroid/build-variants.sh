#!/usr/bin/env bash
# Builds one glMatrix APK per GLES version: apks/glMatrix-ES<v>.apk
# (app id cc.openframeworks.glMatrix.es<v>, launcher name "glMatrix ES <v>")
set -e
cd "$(dirname "$0")"
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17} ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}
mkdir -p apks
for v in ${@:-1.1 2.0 3.0 3.1 3.2}; do
	id=$(echo $v | tr -d .)
	printf '#pragma once\n#define GLMATRIX_DEFAULT_GLES "%s"\n' "$v" > src/glmatrix_variant.h
	sed -i '' -E "s/applicationId \"cc\.openframeworks\.glMatrix[^\"]*\"/applicationId \"cc.openframeworks.glMatrix.es$id\"/" ofApp/build.gradle
	for f in ofApp/src/res/values*/strings.xml; do sed -i '' -E "s#<string name=\"APP_NAME\">[^<]*</string>#<string name=\"APP_NAME\">glMatrix ES $v</string>#" $f; done
	./gradlew assembleDebug --console=plain -q > apks/build-ES$v.log 2>&1 || { echo "ES $v build FAILED (apks/build-ES$v.log)"; exit 1; }
	cp ofApp/build/outputs/apk/playstore/debug/ofApp-playstore-debug.apk apks/glMatrix-ES$v.apk
	echo "built apks/glMatrix-ES$v.apk"
done
