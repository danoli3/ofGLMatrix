"""Guard the CI result contract, including fallback and missing-result failures."""
import unittest
from run import passed, result_line


class Results(unittest.TestCase):
    def test_accepts_actual_requested_context(self):
        for request, got in [('GL 3.3', '4.5 Mesa'), ('ES 2.0', 'OpenGL ES 2.0'), ('ES 1.1', 'OpenGL ES-CM 1.1')]:
            with self.subTest(request=request):
                self.assertTrue(passed(f'GL_MATRIX requested="{request}" got="{got}" RESULT=PASS', request))

    def test_rejects_failure_missing_result_wrong_request_and_fallback(self):
        for line in ['', 'GL_SMOKE_TEST RESULT=PASS',
                     'GL_MATRIX requested="GL 3.3" got="3.3" RESULT=FAIL',
                     'GL_MATRIX requested="GL 2.1" got="4.1" RESULT=PASS',
                     'GL_MATRIX requested="GL 3.3" got="3.2" RESULT=PASS']:
            with self.subTest(line=line):
                self.assertFalse(passed(line, 'GL 3.3'))

    def test_extracts_app_result_from_logcat_and_uses_last_result(self):
        self.assertEqual(result_line('GL_SMOKE_TEST RESULT=PASS\nW/GLMATRIX: GL_MATRIX requested="ES 3.0" RESULT=FAIL'),
                         'W/GLMATRIX: GL_MATRIX requested="ES 3.0" RESULT=FAIL')

    def test_skipped_fbo_checks_do_not_override_the_app_result(self):
        for status in ('PASS', 'FAIL'):
            with self.subTest(status=status):
                line = (f'GL_MATRIX requested="ES 1.1" got="OpenGL ES-CM 1.1" RESULT={status} '
                        '[texture upload/draw/readback=SKIP] [tess2 star (index type + pixels)=SKIP]')
                self.assertEqual(passed(line, 'ES 1.1'), status == 'PASS')


if __name__ == '__main__':
    unittest.main()
