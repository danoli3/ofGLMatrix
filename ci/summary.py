"""Render compact Actions tables from the full diagnostic JSON reports."""
import argparse
import html
import json
import os
from pathlib import Path
import re


def cell(value):
    return html.escape(str(value), quote=False).replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]]) + '\n'


def notes(case):
    detail = case.get('detail', '')
    if 'GL_MATRIX requested=' not in detail:
        # Keep Python command reprs and stack traces in the raw report.
        if 'bootstatus' in detail and 'timed out' in detail:
            return 'Simulator boot / data migration timed out; app tests did not start.'
        return detail[:220] or 'No diagnostic detail.'
    failed = re.findall(r'\[([^\]]+)=FAIL\]', detail)
    if failed:
        return 'Failed checks: ' + '; '.join(failed)
    if case['status'] == 'PASS':
        return 'All applicable rendering checks passed.'
    return 'App result or actual context did not satisfy the requested API.'


def actual_context(detail):
    match = re.search(r'got="([^"]+)"', detail)
    return match.group(1).split(' (')[0] if match else '—'


def planned(platform, abi='', webgl=''):
    if platform in ('linux', 'macos'):
        return [f'GL {v}' for v in ('2.1', '3.2', '3.3', '4.1')]
    if platform == 'ios':
        return [f'ES {v}' for v in ('1.1', '2.0', '3.0')]
    if platform == 'android' and abi == 'x86_64':
        return [f'ES {v}' for v in ('1.1', '2.0', '3.0', '3.1', '3.2')]
    if platform == 'web':
        return [f'WebGL {webgl}']
    return []


def make_report(label, platform, build, runtime, data, abi='', webgl='', sha=''):
    build_status = {'success': 'PASS', 'failure': 'FAIL', 'cancelled': 'CANCELLED'}.get(build, 'NOT RUN')
    build_only = platform == 'macos' or (platform == 'android' and abi == 'arm64-v8a')
    error = data.get('error', '')
    cases = data.get('cases', [])
    # Accept the original browser report as well as the new normalized schema.
    if not cases and data.get('status'):
        cases = [dict(case=f'WebGL {webgl}', status=data['status'], detail=data.get('result', ''))]
    if build_status != 'PASS':
        cases = [dict(case=name, status='NOT RUN', detail='Build did not complete successfully.')
                 for name in planned(platform, abi, webgl)]
    elif build_only:
        reason = ('Hosted macOS VM has no usable OpenGL context.' if platform == 'macos'
                  else 'Physical arm64 device required; emulator coverage is in the x86_64 job.')
        cases = [dict(case='Build only', status='NOT RUN', detail=reason)]
    elif error or not cases:
        reason = notes(dict(detail=error)) if error else f'No runtime report (step: {runtime}).'
        cases = [dict(case=name, status='NOT RUN', detail=reason) for name in planned(platform, abi, webgl)]
        error = reason
    elif runtime != 'success' and not any(case['status'] == 'FAIL' for case in cases):
        error = 'Runtime step failed after producing app results; see the step logs.'
    return dict(job=label, platform=platform, abi=abi, webgl=webgl, openFrameworks=sha,
                build=build_status, build_only=build_only, runtime_step=runtime,
                error=error, cases=cases, context=data.get('context'))


def runtime_status(report):
    if report['build'] != 'PASS':
        return 'NOT RUN'
    if report['build_only']:
        return 'BUILD ONLY'
    if report.get('error'):
        return 'ERROR'
    statuses = [case['status'] for case in report['cases']]
    if 'FAIL' in statuses:
        return 'FAIL'
    if 'NOT RUN' in statuses or not statuses:
        return 'NOT RUN'
    if all(status == 'SKIP' for status in statuses):
        return 'SKIP'
    return 'PASS'


def counts(report):
    if report.get('error'):
        return report['error'][:220]
    if report['build_only']:
        return report['cases'][0]['detail']
    labels = [('PASS', 'passed'), ('FAIL', 'failed'), ('SKIP', 'skipped'), ('NOT RUN', 'not run')]
    return ', '.join(f"{sum(c['status'] == status for c in report['cases'])} {label}"
                     for status, label in labels if any(c['status'] == status for c in report['cases']))


def job_markdown(report):
    text = f"## {cell(report['job'])}\n\n"
    text += table(['Build', 'Runtime', 'Summary'], [[report['build'], runtime_status(report), counts(report)]])
    text += '\n' + table(['Requested API', 'Actual context', 'Result', 'Details'],
                         [[case['case'], actual_context(case.get('detail', '')), case['status'], notes(case)]
                          for case in report['cases']])
    if report.get('context'):
        text += '\n' + table(['Browser context', 'Version', 'Renderer'], [[
            f"WebGL {report['context']['webgl']}", report['context'].get('version', ''), report['context'].get('renderer', '')]])
    raw = json.dumps(report, indent=2)
    text += '\n<details><summary>Full test diagnostics</summary>\n\n<pre>' + html.escape(raw) + '</pre>\n\n</details>\n'
    return text


def aggregate(reports, jobs, sha):
    by_name = {report['job']: report for report in reports}
    rows = []
    cases = []
    for job in jobs:
        if not any(step['name'] == 'Build OF master and the app' for step in job.get('steps', [])):
            continue
        report = by_name.get(job['name'])
        if report:
            rows.append([job['name'], report['build'], runtime_status(report),
                         (job.get('conclusion') or job['status']).upper(), counts(report)])
            cases.extend([[job['name'], case['case'], case['status'], notes(case)] for case in report['cases']])
        else:
            build = next(step.get('conclusion') for step in job['steps'] if step['name'] == 'Build OF master and the app')
            rows.append([job['name'], {'success': 'PASS', 'failure': 'FAIL'}.get(build, 'NOT RUN'),
                         'UNKNOWN', (job.get('conclusion') or job['status']).upper(),
                         'Summary report unavailable. See job logs.'])
    text = '## Graphics matrix results\n\n'
    if sha:
        text += f'Tested [openFrameworks master `{sha[:12]}`](https://github.com/openframeworks/openFrameworks/commit/{sha}).\n\n'
    text += table(['Job', 'Build', 'Runtime', 'Job status', 'Summary'], sorted(rows))
    text += '\n### API test results\n\n' + table(['Job', 'API', 'Result', 'Details'], sorted(cases))
    text += '\n**BUILD ONLY** = compiled without runtime coverage. **SKIP** = unsupported runner capability. **NOT RUN** = tests did not execute. **ERROR** = test infrastructure failed.\n'
    return text


def emit(markdown):
    print(markdown)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(markdown)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    job = sub.add_parser('job')
    job.add_argument('--build', required=True)
    job.add_argument('--runtime', required=True)
    job.add_argument('--out', type=Path, default=Path('artifacts'))
    combined = sub.add_parser('aggregate')
    combined.add_argument('--reports', type=Path, required=True)
    combined.add_argument('--jobs', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'job':
        args.out.mkdir(exist_ok=True)
        path = args.out / 'results.json'
        data = json.loads(path.read_text()) if path.exists() else {}
        report = make_report(os.environ['MATRIX_NAME'], os.environ['CI_PLATFORM'], args.build,
                             args.runtime, data, os.environ.get('ABI', ''), os.environ.get('WEBGL', ''), os.environ.get('OF_SHA', ''))
        report_path = args.out / 'report.json'
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        emit(job_markdown(report))
    else:
        reports = [json.loads(path.read_text()) for path in args.reports.rglob('report.json')]
        emit(aggregate(reports, json.loads(args.jobs.read_text()), os.environ.get('OF_SHA', '')))


if __name__ == '__main__':
    main()
