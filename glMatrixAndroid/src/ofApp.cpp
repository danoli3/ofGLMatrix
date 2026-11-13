#include "ofApp.h"
#include <sys/system_properties.h>
#include <android/log.h>

#include "glmatrix_variant.h" // GLMATRIX_DEFAULT_GLES, generated per APK variant

// One APK per ES version (device farms can't setprop); on a dev device / the
// emulator `adb shell setprop debug.of.gles 3.1` still overrides it.
std::string ofAppRequestedGLES() {
	char value[PROP_VALUE_MAX] = {0};
	if (__system_property_get("debug.of.gles", value) > 0 && value[0]) return value;
	return GLMATRIX_DEFAULT_GLES;
}

void ofApp::setup() {
	core.requested = "ES " + ofAppRequestedGLES();
	core.setup();
}

void ofApp::update() {
	core.update();
}

void ofApp::draw() {
	core.draw();
	if (core.done() && !logged) {
		logged = true;
		__android_log_print(ANDROID_LOG_WARN, "GLMATRIX", "%s", core.resultLine().c_str());
	}
}
