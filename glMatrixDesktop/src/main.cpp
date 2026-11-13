#include "ofMain.h"
#include "../../shared/GLMatrixCore.h"

// OF_GL_VERSION="2.1" | "3.2" | "3.3" | "4.1" ; OF_SHOT=/path/to/screenshot.png
class ofApp : public ofBaseApp {
public:
	GLMatrixCore core;
	std::string shot;
	void setup() override {
		core.requested = "GL " + std::string(getenv("OF_GL_VERSION") ? getenv("OF_GL_VERSION") : "3.2");
		if (getenv("OF_SHOT")) shot = getenv("OF_SHOT");
		core.setup();
	}
	void update() override { core.update(); }
	void draw() override {
		core.draw();
		if (core.done() && !saved) {
			saved = true;
			if (!shot.empty()) ofSaveScreen(shot);
			std::cout << core.resultLine() << std::endl;
			if (!getenv("OF_KEEP")) ofExit(core.allPassed() ? 0 : 1);
		}
	}
	bool saved = false;
};

int main() {
	std::string v = getenv("OF_GL_VERSION") ? getenv("OF_GL_VERSION") : "3.2";
	int major = ofToInt(v.substr(0, v.find('.')));
	int minor = ofToInt(v.substr(v.find('.') + 1));
	ofGLWindowSettings settings;
	settings.setSize(1024, 640);
	settings.windowMode = OF_WINDOW;
	settings.setGLVersion(major, minor);
	ofCreateWindow(settings);
	return ofRunApp(std::make_shared<ofApp>());
}
