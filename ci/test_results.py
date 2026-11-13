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


if __name__ == '__main__':
    unittest.main()
