#include "ofApp.h"

// OF_GLES=1|2|3 (pass as SIMCTL_CHILD_OF_GLES via `xcrun simctl launch`)
int main() {
	ofiOSWindowSettings settings;
	settings.enableRetina = true;
	settings.enableDepth = false;
	settings.enableAntiAliasing = false;
	settings.enableHardwareOrientation = false;
	settings.enableHardwareOrientationAnimation = false;
	const char * v = getenv("OF_GLES");
	int gles = v ? atoi(v) : 2;
	settings.glesVersion = gles == 1 ? OFXIOS_RENDERER_ES1 : gles == 3 ? OFXIOS_RENDERER_ES3 : OFXIOS_RENDERER_ES2;
	ofCreateWindow(settings);
	return ofRunApp(new ofApp);
}
