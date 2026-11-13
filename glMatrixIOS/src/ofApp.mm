#include "ofApp.h"

void ofApp::setup(){
	const char * v = getenv("OF_GLES");
	std::string gles = v ? v : "2";
	core.requested = gles == "1" ? "ES 1.1" : "ES " + gles + ".0";
	core.setup();
}

void ofApp::update(){
	core.update();
}

void ofApp::draw(){
	core.draw();
	if (core.done() && !logged) {
		logged = true;
		printf("%s\n", core.resultLine().c_str());
		fflush(stdout);
	}
}
