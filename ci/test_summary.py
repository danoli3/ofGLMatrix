import unittest
from summary import aggregate, job_markdown, make_report, notes, runtime_status, table
from simulator import select_device


class Summaries(unittest.TestCase):
    def test_rendering_failure_lists_failed_checks_without_log_dump(self):
        detail = 'GL_MATRIX requested="ES 1.1" got="OpenGL ES-CM 1.1 (Driver)" RESULT=FAIL [texture upload/draw/readback=FAIL] [screen readback (graphicsExample)=PASS] [tess2 star (index type + pixels)=FAIL]'
        report = make_report('Android', 'android', 'success', 'failure',
                             dict(cases=[dict(case='ES 1.1', status='FAIL', detail=detail)]), abi='x86_64')
        markdown = job_markdown(report)
        visible = markdown.split('<details>')[0]
        self.assertIn('| PASS | FAIL |', visible)
        self.assertIn('Failed checks: texture upload/draw/readback; tess2 star', visible)
        self.assertNotIn('GL_MATRIX', visible)
        self.assertIn('Full test diagnostics', markdown)

    def test_boot_timeout_is_infrastructure_error_and_all_apis_not_run(self):
        report = make_report('iOS', 'ios', 'success', 'failure',
                             dict(error="Command ['xcrun', 'simctl', 'bootstatus'] timed out after 300 seconds"))
        self.assertEqual(runtime_status(report), 'ERROR')
        self.assertEqual([case['case'] for case in report['cases']], ['ES 1.1', 'ES 2.0', 'ES 3.0'])
        self.assertTrue(all(case['status'] == 'NOT RUN' for case in report['cases']))
        self.assertIn('data migration', report['error'])

    def test_build_only_is_distinct_from_runtime_pass(self):
        report = make_report('macOS', 'macos', 'success', 'not successful', {})
        self.assertEqual(runtime_status(report), 'BUILD ONLY')
        self.assertEqual(report['cases'][0]['status'], 'NOT RUN')

    def test_failed_build_cannot_reuse_successful_runtime_result(self):
        report = make_report('Linux', 'linux', 'failure', 'skipped',
                             dict(cases=[dict(case='GL 3.3', status='PASS', detail='old result')]))
        self.assertEqual(report['build'], 'FAIL')
        self.assertTrue(all(case['status'] == 'NOT RUN' for case in report['cases']))

    def test_tables_escape_delimiters_and_html(self):
        markdown = table(['Check'], [['a|b\n<script>']])
        self.assertIn('a&#124;b<br>&lt;script&gt;', markdown)

    def test_aggregate_includes_missing_report_and_job_failure(self):
        jobs = [dict(name='Linux', status='completed', conclusion='failure',
                     steps=[dict(name='Build OF master and the app', conclusion='failure')])]
        markdown = aggregate([], jobs, 'a' * 40)
        self.assertIn('| Linux | FAIL | UNKNOWN | FAILURE |', markdown)
        report = make_report('Linux', 'linux', 'success', 'success',
                             dict(cases=[dict(case='GL 3.3', status='PASS', detail='All checks passed')]))
        self.assertIn('| Linux | PASS | PASS | FAILURE |', aggregate([report], jobs, 'a' * 40))

    def test_successful_results_do_not_hide_runtime_step_failure(self):
        report = make_report('WebGL 2', 'web', 'success', 'failure',
                             dict(cases=[dict(case='WebGL 2', status='PASS', detail='Checks passed')]), webgl='2')
        self.assertEqual(runtime_status(report), 'ERROR')

    def test_simulator_uses_latest_available_ios_and_prefers_booted_phone(self):
        devices = {
            'com.apple.CoreSimulator.SimRuntime.iOS-18-0': [dict(name='iPhone 16', udid='old', isAvailable=True, state='Booted')],
            'com.apple.CoreSimulator.SimRuntime.iOS-26-5': [
                dict(name='iPhone 17', udid='new-off', isAvailable=True, state='Shutdown'),
                dict(name='iPhone Air', udid='new-on', isAvailable=True, state='Booted')],
        }
        self.assertEqual(select_device(devices)['udid'], 'new-on')


if __name__ == '__main__':
    unittest.main()
