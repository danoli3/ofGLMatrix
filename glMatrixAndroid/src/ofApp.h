#pragma once

#include "ofMain.h"
#include "ofxAndroid.h"
#include "GLMatrixCore.h"

std::string ofAppRequestedGLES();

class ofApp : public ofxAndroidApp {
public:
	void setup() override;
	void update() override;
	void draw() override;

private:
	GLMatrixCore core;
	bool logged = false;
};
