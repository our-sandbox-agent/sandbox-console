"""Exercise no-contact guards and prove ready never means runtime go."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("preflight", Path(__file__).with_name("gvisor-preflight.py"))
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
DIGEST = "diagnostic@sha256:" + "a" * 64


class PreflightTests(unittest.TestCase):
    def test_non_linux_never_contacts_docker(self):
        with patch.object(preflight.platform, "system", return_value="Darwin"), patch.object(preflight.subprocess, "run") as run:
            result = preflight.collect("unix:///var/run/docker.sock", DIGEST)
            run.assert_not_called()
            self.assertEqual(result["verdict"], "blocked_environment")

    def test_remote_socket_or_unpinned_image_never_contacts_docker(self):
        with patch.object(preflight.platform, "system", return_value="Linux"), patch.object(preflight.subprocess, "run") as run:
            for socket, image in [(None, DIGEST), ("tcp://remote:2375", DIGEST), ("unix:///docker.sock", "image:latest")]:
                self.assertTrue(preflight.collect(socket, image)["blockers"])
            run.assert_not_called()

    def test_ready_is_not_go_and_context_cannot_redirect(self):
        replies = ["29", "linux", "2", "systemd", '{"runsc":{}}', "runsc version test", "sha256:image"]
        completed = [subprocess.CompletedProcess([], 0, stdout=x) for x in replies]
        with patch.object(preflight.platform, "system", return_value="Linux"), patch.object(preflight.shutil, "which", return_value="/bin/tool"), patch.dict(preflight.os.environ, {"DOCKER_CONTEXT": "remote", "DOCKER_HOST": "tcp://remote:2375"}), patch.object(preflight.subprocess, "run", side_effect=completed) as run:
            result = preflight.collect("unix:///docker.sock", DIGEST)
            self.assertEqual(result["verdict"], "ready_for_manual_matrix_not_go")
            self.assertEqual(result["matrix_verdict"], "not_run")
            for call in run.call_args_list:
                self.assertNotIn("DOCKER_CONTEXT", call.kwargs["env"])
                self.assertNotIn("DOCKER_HOST", call.kwargs["env"])
                args = call.args[0]
                if args[0] == "docker":
                    self.assertEqual(args[1:3], ["--host", "unix:///docker.sock"])
                    self.assertIn(args[3], ("version", "info", "image"))

    def test_failure_does_not_leak_stderr(self):
        with patch.object(preflight.platform, "system", return_value="Linux"), patch.object(preflight.shutil, "which", return_value="/bin/tool"), patch.object(preflight.subprocess, "run", side_effect=subprocess.CalledProcessError(1, [], stderr="SECRET")):
            result = preflight.collect("unix:///docker.sock", DIGEST)
            self.assertEqual(result["verdict"], "blocked_environment")
            self.assertNotIn("SECRET", str(result))


if __name__ == "__main__":
    unittest.main()
