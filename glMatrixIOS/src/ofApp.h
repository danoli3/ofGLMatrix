#pragma once

#include "ofxiOS.h"
#include "GLMatrixCore.h"

class ofApp : public ofxiOSApp {
public:
	void setup();
	void update();
	void draw();
private:
	GLMatrixCore core;
	bool logged = false;
};
