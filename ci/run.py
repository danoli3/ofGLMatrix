#!/usr/bin/env python3
"""Run real app cases; missing results and timeouts are failures, never passes."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts'
VERSIONS = ('1.1', '2.0', '3.0', '3.1', '3.2')


def result_line(log):
    lines = [line for line in log.splitlines() if 'GL_MATRIX requested=' in line]
    return lines[-1] if lines else ''


def passed(line, requested):
    if f'requested="{requested}"' not in line or ' RESULT=PASS' not in line:
        return False
    # A fallback may draw successfully but does not cover the requested API.
    got = re.search(r'got="(?:OpenGL ES(?:-CM)?\s+)?(\d+)\.(\d+)', line)
    want = re.search(r'(\d+)\.(\d+)', requested)
    return bool(got and want and tuple(map(int, got.groups())) >= tuple(map(int, want.groups())))


def capture(command, path, env=None, timeout=120, until_result=False):
    with path.open('w') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                if until_result and result_line(path.read_text(errors='replace')):
                    return 0
                code = process.poll()
                if code is not None:
                    return code
                time.sleep(0.5)
            with path.open('a') as log:
                log.write('\nCI timeout waiting for app result\n')
            return 124
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def check(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def desktop():
    binary = ROOT / 'glMatrixDesktop/bin/glMatrixDesktop'
    if sys.platform == 'darwin':
        binary = ROOT / 'glMatrixDesktop/bin/glMatrixDesktop.app/Contents/MacOS/glMatrixDesktop'
    cases = []
    for version in ('2.1', '3.2', '3.3', '4.1'):
        log = OUT / f'GL-{version}.log'
        env = dict(os.environ, OF_GL_VERSION=version, OF_SHOT=str(OUT / f'GL-{version}.png'))
        env.pop('OF_KEEP', None)
        code = capture([str(binary)], log, env=env)
        line = result_line(log.read_text(errors='replace'))
        cases.append(dict(case=f'GL {version}', status='PASS' if code == 0 and passed(line, f'GL {version}') else 'FAIL', detail=line or f'No result (exit {code})'))
    return cases


def ios():
    app = OUT / 'ios-app/glRenderSmokeTest.app'
    bundle = check(['/usr/libexec/PlistBuddy', '-c', 'Print CFBundleIdentifier', str(app / 'Info.plist')])
    devices = json.loads(check(['xcrun', 'simctl', 'list', 'devices', 'available', '--json']))['devices']
    phones = [device for runtime, group in devices.items() if '.iOS-' in runtime
              for device in group if device['name'].startswith('iPhone') and device['isAvailable']]
    if not phones:
        raise RuntimeError('No available iPhone simulator')
    device = phones[0]
    udid = device['udid']
    if device['state'] != 'Booted':
        subprocess.run(['xcrun', 'simctl', 'boot', udid], check=True)
    subprocess.run(['xcrun', 'simctl', 'bootstatus', udid, '-b'], check=True, timeout=300)
    subprocess.run(['xcrun', 'simctl', 'install', udid, str(app)], check=True)
    cases = []
    for value, version in (('1', '1.1'), ('2', '2.0'), ('3', '3.0')):
        log = OUT / f'iOS-ES-{version}.log'
        try:
            code = capture(['xcrun', 'simctl', 'launch', '--console', udid, bundle], log,
                           env=dict(os.environ, SIMCTL_CHILD_OF_GLES=value), until_result=True)
            line = result_line(log.read_text(errors='replace'))
            cases.append(dict(case=f'ES {version}', status='PASS' if code == 0 and passed(line, f'ES {version}') else 'FAIL', detail=line or f'No result (exit {code})'))
            subprocess.run(['xcrun', 'simctl', 'io', udid, 'screenshot', str(OUT / f'iOS-ES-{version}.png')], check=False)
        finally:
            subprocess.run(['xcrun', 'simctl', 'terminate', udid, bundle], check=False)
    return cases


def android():
    apk = OUT / 'glMatrix-x86_64.apk'
    sdk = Path(os.environ['ANDROID_HOME'])
    aapt = sdk / 'build-tools/37.0.0/aapt'
    package = re.search(r"package: name='([^']+)'", check([str(aapt), 'dump', 'badging', str(apk)])).group(1)
    subprocess.run(['adb', 'install', '-r', str(apk)], check=True)
    encoded = check(['adb', 'shell', 'getprop', 'ro.opengles.version'])
    maximum = (int(encoded) >> 16, int(encoded) & 0xffff)
    cases = []
    try:
        for version in VERSIONS:
            # This is a declared runner capability skip, not an app test pass.
            if tuple(map(int, version.split('.'))) > maximum:
                cases.append(dict(case=f'ES {version}', status='SKIP', detail=f'Emulator advertises ES {maximum[0]}.{maximum[1]}; requires a capable device'))
                continue
            log = OUT / f'Android-ES-{version}.log'
            subprocess.run(['adb', 'shell', 'am', 'force-stop', package], check=True)
            subprocess.run(['adb', 'shell', 'setprop', 'debug.of.gles', version], check=True)
            subprocess.run(['adb', 'logcat', '-c'], check=True)
            subprocess.run(['adb', 'shell', 'am', 'start', '-W', '-n', f'{package}/cc.openframeworks.android.OFActivity'], check=True)
            code = capture(['adb', 'logcat', '-v', 'brief'], log, until_result=True)
            line = result_line(log.read_text(errors='replace'))
            cases.append(dict(case=f'ES {version}', status='PASS' if code == 0 and passed(line, f'ES {version}') else 'FAIL', detail=line or f'No result (exit {code})'))
            with (OUT / f'Android-ES-{version}.png').open('wb') as image:
                subprocess.run(['adb', 'exec-out', 'screencap', '-p'], stdout=image, check=False)
    finally:
        subprocess.run(['adb', 'shell', 'setprop', 'debug.of.gles', ''], check=False)
        subprocess.run(['adb', 'shell', 'am', 'force-stop', package], check=False)
    if not any(case['status'] != 'SKIP' for case in cases):
        raise RuntimeError('Emulator provided no usable GLES versions')
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('platform', choices=('desktop', 'ios', 'android'))
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    try:
        cases = globals()[args.platform]()
    except Exception as error:
        cases = [dict(case=args.platform, status='FAIL', detail=str(error))]
    report = dict(platform=args.platform, openFrameworks=os.environ.get('OF_SHA', ''), cases=cases)
    (OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    summary = '\n'.join(f"- **{case['status']}** {case['case']}: {case['detail']}" for case in cases)
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(f'### {args.platform}\n\n{summary}\n')
    return int(any(case['status'] == 'FAIL' for case in cases))


if __name__ == '__main__':
    sys.exit(main())
