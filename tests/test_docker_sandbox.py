import unittest
import os
import shutil
import docker
from src.sandbox.docker_runner import DockerSandbox

class TestDockerSandbox(unittest.TestCase):
    def setUp(self):
        self.job_id = "test_job_123"
        self.work_dir = f"storage/sandbox/{self.job_id}"
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
        os.makedirs(self.work_dir, exist_ok=True)
        try:
            self.sandbox = DockerSandbox(self.job_id, self.work_dir)
        except docker.errors.DockerException as exc:
            self.skipTest(f"Docker daemon unavailable: {exc}")

    def tearDown(self):
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)

    def test_simple_execution(self):
        code = "print('Hello Sandbox')"
        exit_code, stdout, stderr = self.sandbox.run_code(code)
        self.assertEqual(exit_code, 0)
        self.assertIn("Hello Sandbox", stdout)

    def test_file_write(self):
        code = """
with open('output.txt', 'w') as f:
    f.write('Persistent Data')
print('Done')
"""
        exit_code, stdout, stderr = self.sandbox.run_code(code)
        self.assertEqual(exit_code, 0)
        
        # Check if file exists on host
        output_path = os.path.join(self.work_dir, "output.txt")
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r") as f:
            self.assertEqual(f.read(), "Persistent Data")

    def test_network_isolation(self):
        code = """
import urllib.request
try:
    urllib.request.urlopen('http://google.com', timeout=2)
    print('Connected')
except Exception as e:
    print(f'Failed: {e}')
"""
        exit_code, stdout, stderr = self.sandbox.run_code(code)
        self.assertIn("Failed", stdout + stderr)
        self.assertNotIn("Connected", stdout)

    def test_read_only_root(self):
        code = """
try:
    with open('/etc/hack.txt', 'w') as f:
        f.write('hacked')
    print('Success')
except Exception as e:
    print(f'Failed: {e}')
"""
        exit_code, stdout, stderr = self.sandbox.run_code(code)
        self.assertIn("Failed", stdout + stderr)
        self.assertIn("Read-only file system", stdout + stderr)

if __name__ == '__main__':
    unittest.main()
