"""Warm the latest available iOS simulator while the app builds."""
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parents[1] / 'artifacts'
BOOT_TIMEOUT = 900


def select_device(devices):
    runtimes = sorted((runtime for runtime in devices if '.iOS-' in runtime),
                      key=lambda runtime: tuple(map(int, re.findall(r'\d+', runtime))), reverse=True)
    for runtime in runtimes:
        phones = [device for device in devices[runtime] if device['name'].startswith('iPhone') and device.get('isAvailable')]
        if phones:
            phone = next((device for device in phones if device['state'] == 'Booted'), phones[0])
            return dict(phone, runtime=runtime)
    raise RuntimeError('No available iPhone simulator')


def prepare():
    OUT.mkdir(exist_ok=True)
    listing = subprocess.check_output(['xcrun', 'simctl', 'list', 'devices', 'available', '--json'], text=True)
    device = select_device(json.loads(listing)['devices'])
    (OUT / 'simulator.json').write_text(json.dumps(device, indent=2) + '\n')
    if device['state'] != 'Booted':
        subprocess.run(['xcrun', 'simctl', 'boot', device['udid']], check=True, timeout=60)
    print(f"Started {device['name']} ({device['runtime']}); migration can proceed during compilation.")
    return device


def ready():
    metadata = OUT / 'simulator.json'
    device = json.loads(metadata.read_text()) if metadata.exists() else prepare()
    try:
        with (OUT / 'simulator-boot.log').open('w') as log:
            subprocess.run(['xcrun', 'simctl', 'bootstatus', device['udid'], '-b'],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=BOOT_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f'Simulator boot / data migration timed out after {BOOT_TIMEOUT}s; app tests did not start. See simulator-boot.log.') from error
    return device


if __name__ == '__main__':
    prepare()
