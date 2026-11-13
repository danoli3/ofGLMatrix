#include "ofMain.h"
#include "../../shared/GLMatrixCore.h"
#include <emscripten.h>

// index.html?webgl=2 (default, WebGL 2 = ES 3.0) or ?webgl=1 with WebGL 2
// disabled in the browser (ofxAppEmscriptenWindow falls back to WebGL 1 = ES 2.0)
class ofApp : public ofBaseApp {
public:
	GLMatrixCore core;
	bool logged = false;
	void setup() override {
		int webgl = EM_ASM_INT({
			var m = /[?&]webgl=([12])/.exec(window.location.search);
			return m ? parseInt(m[1]) : 2;
		});
		core.requested = webgl == 1 ? "ES 2.0" : "ES 3.0";
		core.setup();
	}
	void update() override { core.update(); }
	void draw() override {
		core.draw();
		if (core.done() && !logged) {
			logged = true;
			std::string line = core.resultLine();
			std::cout << line << std::endl;
			EM_ASM({ document.title = UTF8ToString($0); }, line.c_str());
		}
	}
};

int main() {
	ofGLESWindowSettings settings;
	settings.setSize(1024, 640);
	ofCreateWindow(settings);
	return ofRunApp(std::make_shared<ofApp>());
}
