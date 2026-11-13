#pragma once

// GL matrix test: draws graphicsExample's scene plus a HUD of checks, for
// every GL / GLES version the platform can create. Shared by the desktop,
// iOS, Android and emscripten bridges; only main() picks the version.

#include "ofMain.h"
#include "GLSmokeTestCore.h"

class GLMatrixCore {
public:
	struct Check {
		std::string name;
		std::string status; // PASS / FAIL / n/a
		std::string detail;
	};

	std::string requested;   // e.g. "GL 3.3" / "ES 2.0"
	int framesBeforeResult = 30;

	void setup() {
		counter = 0;
		ofSetCircleResolution(50);
		ofBackground(255, 255, 255);
		ofSetFrameRate(60);
		ofSeedRandom(8533);

		auto r = ofGetGLRenderer();
		glVersion = safeGLString(GL_VERSION);
		glRenderer = safeGLString(GL_RENDERER);
#ifdef GL_SHADING_LANGUAGE_VERSION
		glsl = ofIsGLProgrammableRenderer() ? safeGLString(GL_SHADING_LANGUAGE_VERSION) : "n/a (fixed function)";
#else
		glsl = "n/a (fixed function)";
#endif
		traceGL("before setup (window/renderer creation)");
		ofMajor = r ? r->getGLVersionMajor() : 0;
		ofMinor = r ? r->getGLVersionMinor() : 0;
		rendererName = ofIsGLProgrammableRenderer() ? "ofGLProgrammableRenderer" : "ofGLRenderer (fixed)";

		traceGL("glGetString");
		logFBState("setup before FBOs");
		smoke.allocate();
		traceGL("smoke.allocate");
		logFBState("after smoke.allocate");
		runResourceChecks();
		traceGL("runResourceChecks");
		logFBState("after runResourceChecks");
	}

	void update() {
		counter += 0.033f;
	}

	void draw() {
		const float s = std::min(ofGetWidth() / 840.f, (ofGetHeight() - 250.f) / 300.f);
		ofPushMatrix();
		ofTranslate(0, 250.f - 230.f * s);
		ofScale(s, s);
		traceGL("start of draw");
		if (frame < 2) logFBState("start of draw");
		drawGraphicsExample();
		ofPopMatrix();
		traceGL("drawGraphicsExample");

		ofPushStyle();
		smoke.drawFrame(); // FBO top-left, tessellated star at (180,160)
		ofPopStyle();
		traceGL("smoke.drawFrame");
		if (frame < 2) logFBState("after smoke.drawFrame");
		if (smoke.finished() && !smokeRecorded) {
			smokeRecorded = true;
			checks.push_back({"smoke: indexed VBO + tess2 path + FBO readback", smoke.passed() ? "PASS" : "FAIL", smoke.resultLine()});
		}

		if (frame == framesBeforeResult) {
			screenCheck();
			finalize();
		}
		drawHUD();
		traceGL("drawHUD");
		++frame;
	}

	bool done() const { return finalized; }
	bool allPassed() const {
		for (auto & c : checks) if (c.status == "FAIL") return false;
		return finalized;
	}

	std::string resultLine() const {
		std::string line = "GL_MATRIX requested=\"" + requested + "\" got=\"" + glVersion + "\" glsl=\"" + glsl
			+ "\" renderer=\"" + rendererName + "\" device=\"" + glRenderer + "\" RESULT=" + (allPassed() ? "PASS" : "FAIL");
		for (auto & c : checks) line += " [" + c.name + "=" + c.status + "]";
		return line;
	}

private:

	// one-off probe of renderer / texture calls, each followed by glGetError
	void probeGL() {
		while (glGetError() != GL_NO_ERROR) {}
		auto r = ofGetGLRenderer();
		auto t = [&](const char * w){ GLenum e; while ((e = glGetError()) != GL_NO_ERROR) ofLogNotice("glMatrix") << "GL_MATRIX_PROBE " << w << " -> " << ofToHex(e); };
#ifdef TARGET_OPENGLES
		{ GLint fb = 0; glGetIntegerv(GL_FRAMEBUFFER_BINDING, &fb); t("glGetIntegerv(GL_FRAMEBUFFER_BINDING)"); }
#endif
		r->viewport(); t("renderer->viewport()");
		r->setupScreenPerspective(); t("setupScreenPerspective()");
		r->setupScreenOrtho(); t("setupScreenOrtho()");
		r->setupScreen(); t("setupScreen()");
		ofClear(255, 255, 255, 255); t("ofClear");
		ofBackground(255); t("ofBackground");
		r->startRender(); t("startRender()");
		r->finishRender(); t("finishRender()");
		ofPushMatrix(); ofTranslate(1, 1); ofScale(1, 1); ofPopMatrix(); t("push/translate/scale/pop");
		{ ofPixels px; px.allocate(8, 8, OF_PIXELS_GRAY_ALPHA); px.set(0); ofTexture tx; tx.allocate(px); t("ofTexture allocate GRAY_ALPHA"); tx.loadData(px); t("ofTexture loadData GRAY_ALPHA");
		  tx.setTextureMinMagFilter(GL_LINEAR, GL_NEAREST); t("setTextureMinMagFilter"); tx.setTextureWrap(GL_CLAMP_TO_EDGE, GL_CLAMP_TO_EDGE); t("setTextureWrap");
		  tx.draw(0, 0); t("ofTexture draw GRAY_ALPHA"); }
		{ ofPixels px; px.allocate(8, 8, OF_PIXELS_GRAY); px.set(0); ofTexture tx; tx.loadData(px); t("ofTexture loadData GRAY"); }
		{ ofPixels px; px.allocate(8, 8, OF_PIXELS_GRAY_ALPHA);
		  ofLogNotice("glMatrix") << "GL_MATRIX_PROBE GRAY_ALPHA internal=" << ofToHex(ofGetGLInternalFormat(px)) << " format=" << ofToHex(ofGetGLFormat(px)) << " type=" << ofToHex(ofGetGLType(px));
		  ofPixels g; g.allocate(8, 8, OF_PIXELS_GRAY);
		  ofLogNotice("glMatrix") << "GL_MATRIX_PROBE GRAY internal=" << ofToHex(ofGetGLInternalFormat(g)) << " format=" << ofToHex(ofGetGLFormat(g)) << " type=" << ofToHex(ofGetGLType(g)); }
		{ GLuint id; glGenTextures(1, &id); glBindTexture(GL_TEXTURE_2D, id); t("raw genTextures/bind");
		  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE_ALPHA, 8, 8, 0, GL_LUMINANCE_ALPHA, GL_UNSIGNED_BYTE, nullptr); t("raw glTexImage2D LUMINANCE_ALPHA");
		  glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, 8, 8, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, nullptr); t("raw glTexImage2D LUMINANCE");
		  unsigned char buf[256] = {0};
		  for (int a : {1, 2, 4, 8}) { glPixelStorei(GL_UNPACK_ALIGNMENT, a); std::string w = "raw glPixelStorei(UNPACK_ALIGNMENT," + ofToString(a) + ")"; t(w.c_str()); }
		  glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
		  glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 8, 8, GL_LUMINANCE, GL_UNSIGNED_BYTE, buf); t("raw glTexSubImage2D LUMINANCE");
		  glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR); t("raw glTexParameterf MIN_FILTER");
		  glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE); t("raw glTexEnvf MODULATE");
		  glBindTexture(GL_TEXTURE_2D, 0); glDeleteTextures(1, &id); }
		ofDrawBitmapString("probe", 10, 10); t("ofDrawBitmapString (1st)");
		ofDrawBitmapString("probe", 10, 10); t("ofDrawBitmapString (2nd)");
		ofLogNotice("glMatrix") << "GL_MATRIX_PROBE done";
	}
	void logFBState(const char * where) {
		GLint fb = -1, vp[4] = {0,0,0,0};
		glGetIntegerv(GL_FRAMEBUFFER_BINDING, &fb);
		glGetIntegerv(GL_VIEWPORT, vp);
		ofLogNotice("glMatrix") << "GL_MATRIX_FB " << where << " binding=" << fb << " viewport=" << vp[0] << "," << vp[1] << "," << vp[2] << "," << vp[3];
	}

	// GL_MATRIX_TRACE: report glGetError after each step during setup + first 2 frames
	void traceGL(const char * where) {
		if (frame > 1) return;
		GLenum e;
		while ((e = glGetError()) != GL_NO_ERROR) {
			ofLogNotice("glMatrix") << "GL_MATRIX_TRACE frame=" << frame << " " << where << " -> " << ofToHex(e);
		}
	}

	static std::string safeGLString(GLenum e) {
		const GLubyte * s = glGetString(e);
		return s ? std::string(reinterpret_cast<const char *>(s)) : std::string("?");
	}

	void runResourceChecks() {
		// 1. context version matches what was asked for
		{
			Check c{"context version", "PASS", "of=" + ofToString(ofMajor) + "." + ofToString(ofMinor) + " GL_VERSION=" + glVersion};
			int reqMajor = 0, reqMinor = 0;
			std::string nums = requested.substr(requested.find(' ') + 1);
			reqMajor = ofToInt(nums.substr(0, nums.find('.')));
			reqMinor = ofToInt(nums.substr(nums.find('.') + 1));
#ifdef TARGET_OPENGLES
			// ES: the renderer must be set up at the requested ES major
			if (ofMajor != reqMajor) c.status = "FAIL";
#else
			if (reqMajor >= 3) {
				// core profile: driver may hand back a newer version, never older
				if (!ofIsGLProgrammableRenderer() || ofMajor * 10 + ofMinor < reqMajor * 10 + reqMinor) c.status = "FAIL";
			} else if (ofIsGLProgrammableRenderer()) {
				c.status = "FAIL"; // GL 2.1 should use the fixed-function renderer
			}
#endif
			checks.push_back(c);
		}

		// 2. texture upload -> draw into FBO -> readback
		{
			Check c{"texture upload/draw/readback", "FAIL", ""};
			ofPixels px;
			px.allocate(4, 4, OF_PIXELS_RGBA);
			px.setColor(ofColor(255, 0, 255, 255));
			ofTexture tex;
			tex.loadData(px);
			traceGL("texture loadData");
			ofFbo fbo;
			fbo.allocate(16, 16, GL_RGBA);
			fbo.begin();
			ofClear(0, 0, 0, 255);
			ofSetColor(255);
			tex.draw(0, 0, 16, 16);
			fbo.end();
			ofPixels out;
			fbo.readToPixels(out);
			if (out.isAllocated()) {
				ofColor col = out.getColor(8, 8);
				c.detail = "center=" + ofToString(col);
				if (col.r > 200 && col.g < 60 && col.b > 200) c.status = "PASS";
			} else {
				c.detail = "no pixels";
			}
			checks.push_back(c);
		}

		// 3. shader compile/link + draw (programmable renderers only)
		{
			Check c{"shader compile/link/draw", "n/a", "fixed-function renderer"};
			if (ofIsGLProgrammableRenderer()) {
				c.status = "FAIL";
				std::string vs, fs;
#ifdef TARGET_OPENGLES
				if (ofMajor >= 3) {
					vs = "#version 300 es\nuniform mat4 modelViewProjectionMatrix;\nin vec4 position;\nvoid main(){ gl_Position = modelViewProjectionMatrix * position; }\n";
					fs = "#version 300 es\nprecision mediump float;\nout vec4 outColor;\nvoid main(){ outColor = vec4(0.0, 1.0, 1.0, 1.0); }\n";
				} else {
					vs = "uniform mat4 modelViewProjectionMatrix;\nattribute vec4 position;\nvoid main(){ gl_Position = modelViewProjectionMatrix * position; }\n";
					fs = "precision mediump float;\nvoid main(){ gl_FragColor = vec4(0.0, 1.0, 1.0, 1.0); }\n";
				}
#else
				vs = "#version 150\nuniform mat4 modelViewProjectionMatrix;\nin vec4 position;\nvoid main(){ gl_Position = modelViewProjectionMatrix * position; }\n";
				fs = "#version 150\nout vec4 outColor;\nvoid main(){ outColor = vec4(0.0, 1.0, 1.0, 1.0); }\n";
#endif
				ofShader shader;
				bool ok = shader.setupShaderFromSource(GL_VERTEX_SHADER, vs)
					&& shader.setupShaderFromSource(GL_FRAGMENT_SHADER, fs)
					&& shader.bindDefaults()
					&& shader.linkProgram();
				if (ok) {
					ofFbo fbo;
					fbo.allocate(16, 16, GL_RGBA);
					fbo.begin();
					ofClear(0, 0, 0, 255);
					shader.begin();
					ofDrawRectangle(0, 0, 16, 16);
					shader.end();
					fbo.end();
					ofPixels out;
					fbo.readToPixels(out);
					ofColor col = out.isAllocated() ? out.getColor(8, 8) : ofColor(0);
					c.detail = "center=" + ofToString(col);
					if (col.r < 60 && col.g > 200 && col.b > 200) c.status = "PASS";
				} else {
					c.detail = "compile/link failed";
				}
			}
			checks.push_back(c);
		}
	}

	void screenCheck() {
		// read back the window where graphicsExample drew its orange circle
		Check c{"screen readback (graphicsExample)", "FAIL", ""};
		const float s = std::min(ofGetWidth() / 840.f, (ofGetHeight() - 250.f) / 300.f);
		const int x = static_cast<int>(100 * s);
		const int y = static_cast<int>(250.f - 230.f * s + 400 * s);
		ofImage img;
		img.grabScreen(x - 4, y - 4, 8, 8);
		if (img.isAllocated()) {
			ofColor col = img.getColor(4, 4);
			c.detail = "circle=" + ofToString(col);
			if (col.r > 200 && col.g > 90 && col.g < 180 && col.b < 60) c.status = "PASS";
		} else {
			c.detail = "grabScreen failed";
		}
		checks.push_back(c);

		// the smoke test's tessellated 6-point star (drawn at 180,160): its left
		// arm is only filled when the tess2 index type matches ofIndexType
		{
			Check t{"tess2 star (index type + pixels)", "FAIL", ""};
			ofPath star;
			star.setFilled(true);
			star.setPolyWindingMode(OF_POLY_WINDING_ODD);
			for (int i = 0; i < 12; ++i) {
				const float radius = (i % 2 == 0) ? 55.f : 22.f;
				const float angle = ofDegToRad(i * 30.f - 90.f);
				const glm::vec2 p(std::cos(angle) * radius, std::sin(angle) * radius);
				if (i == 0) star.moveTo(p); else star.lineTo(p);
			}
			star.close();
			const ofMesh & m = star.getTessellation();
			bool indicesOk = m.getNumIndices() > 0 && m.getNumIndices() % 3 == 0;
			for (auto i : m.getIndices()) if (i >= m.getNumVertices()) indicesOk = false;
			// a triangle with a repeated vertex is the signature of 32-bit
			// indices read as 16-bit (0 0 1 0 2 0 ...)
			for (size_t i = 0; i + 2 < m.getNumIndices(); i += 3) {
				auto a = m.getIndex(i), b = m.getIndex(i + 1), c = m.getIndex(i + 2);
				if (a == b || b == c || a == c) indicesOk = false;
			}
			ofImage arm;
			arm.grabScreen(180 - 35 - 2, 140 - 2, 4, 4);
			ofColor col = arm.isAllocated() ? arm.getColor(2, 2) : ofColor(0);
			bool armOk = col.r > 200 && col.g > 100 && col.g < 180 && col.b < 60;
			t.detail = "verts=" + ofToString(m.getNumVertices()) + " indices=" + ofToString(m.getNumIndices())
				+ " sizeof(ofIndexType)=" + ofToString(sizeof(ofIndexType)) + " arm=" + ofToString(col);
			t.detail += " first=";
			for (size_t i = 0; i < std::min<size_t>(12, m.getNumIndices()); ++i) t.detail += ofToString(m.getIndex(i)) + " ";
			if (indicesOk && armOk) t.status = "PASS";
			checks.push_back(t);
		}

		Check e{"no GL errors", "PASS", ""};
		GLenum err;
		int n = 0;
		while ((err = glGetError()) != GL_NO_ERROR) { ++n; e.detail = "last=" + ofToHex(err); }
		if (n) e.status = "FAIL";
		checks.push_back(e);
	}

	void finalize() {
		finalized = true;
		ofLogNotice("glMatrix") << resultLine();
		for (auto & c : checks) {
			if (c.status == "FAIL") ofLogNotice("glMatrix") << "GL_MATRIX_DETAIL " << c.name << ": " << c.detail;
		}
	}

	void drawGraphicsExample() {
		ofSetColor(255, 130, 0);
		float radius = 50 + 10 * std::sin(counter);
		ofFill();
		ofDrawCircle(100, 400, radius);
		traceGL("ofDrawCircle filled");
		ofNoFill();
		ofSetHexColor(0xCCCCCC);
		ofDrawCircle(100, 400, 80);
		traceGL("ofDrawCircle outline (ofNoFill)");
		ofSetHexColor(0x000000);
		ofDrawBitmapString("circle", 75, 500);
		traceGL("ofDrawBitmapString");

		ofFill();
		for (int i = 0; i < 200; i++) {
			ofSetColor((int)ofRandom(0, 255), (int)ofRandom(0, 255), (int)ofRandom(0, 255));
			ofDrawRectangle(ofRandom(250, 350), ofRandom(350, 450), ofRandom(10, 20), ofRandom(10, 20));
		}
		ofSetHexColor(0x000000);
		traceGL("200 x ofDrawRectangle");
		ofDrawBitmapString("rectangles", 275, 500);

		ofSetHexColor(0x00FF33);
		ofDrawRectangle(400, 350, 100, 100);
		ofEnableAlphaBlending();
		ofSetColor(255, 0, 0, 127);
		ofDrawRectangle(450, 430, 100, 33);
		ofSetColor(255, 0, 0, (int)(counter * 10.0f) % 255);
		ofDrawRectangle(450, 370, 100, 33);
		ofDisableAlphaBlending();
		traceGL("alpha blending rects");
		ofSetHexColor(0x000000);
		ofDrawBitmapString("transparency", 410, 500);

		ofSetHexColor(0xFF0000);
		for (int i = 0; i < 20; i++) {
			ofDrawLine(600, 300 + (i * 5), 800, 250 + (i * 10));
		}
		traceGL("ofDrawLine x20");
		ofSetHexColor(0x000000);
		ofDrawBitmapString("lines", 600, 500);
	}

	void drawHUD() {
		ofPushStyle();
		ofSetColor(0);
		float x = 270, y = 18;
		ofDrawBitmapString("requested: " + requested + "   renderer: " + rendererName, x, y); y += 15;
		ofDrawBitmapString("GL_VERSION: " + glVersion, x, y); y += 15;
		ofDrawBitmapString("GLSL: " + glsl, x, y); y += 15;
		ofDrawBitmapString("device: " + glRenderer.substr(0, 60), x, y); y += 20;
		for (auto & c : checks) {
			ofSetColor(c.status == "PASS" ? ofColor(0, 140, 0) : c.status == "FAIL" ? ofColor(200, 0, 0) : ofColor(110));
			ofDrawBitmapString("[" + c.status + "] " + c.name, x, y);
			y += 15;
		}
		if (finalized) {
			ofSetColor(allPassed() ? ofColor(0, 140, 0) : ofColor(200, 0, 0));
			ofDrawBitmapString(allPassed() ? "RESULT: PASS" : "RESULT: FAIL", x, y + 5);
		}
		ofPopStyle();
	}

	GLSmokeTestCore smoke;
	std::vector<Check> checks;
	std::string glVersion, glRenderer, glsl, rendererName;
	int ofMajor = 0, ofMinor = 0;
	float counter = 0;
	int frame = 0;
	bool smokeRecorded = false;
	bool finalized = false;
};
