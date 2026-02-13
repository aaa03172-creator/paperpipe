import docker
import os
import tarfile
import io
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class DockerSandbox:
    """
    Secure Docker Sandbox for executing untrusted Python code.
    Enforces strict isolation: No network, Read-only root, Memory limits.
    """
    def __init__(self, job_id: str, work_dir: str):
        self.job_id = job_id
        self.host_work_dir = os.path.abspath(work_dir)
        self.client = docker.from_env()
        self.container_name = f"paperpipe_sandbox_{job_id}"
        self.image = "python:3.10-slim" # Lightweight, standard python image
        
        # Ensure host work dir exists
        os.makedirs(self.host_work_dir, exist_ok=True)

    def run_code(self, code: str, timeout_sec: int = 30) -> Tuple[int, str, str]:
        """
        Runs Python code in the sandbox.
        Returns: (exit_code, stdout, stderr)
        """
        # 1. Write code to host work dir
        script_path = os.path.join(self.host_work_dir, "script.py")
        with open(script_path, "w") as f:
            f.write(code)
            
        container = None
        try:
            # 2. Run Container with Strict Security
            # - network_mode="none": No internet
            # - mem_limit="512m": Prevent DOS
            # - read_only=True: Root FS is immutable
            # - volumes: Bind mount host workdir to /work (RW)
            # - working_dir: /work
            # - user: 1000:1000 (Recommended, but requires image setup. skipping for simple python:slim for now, relying on container isolation)
            
            logger.info(f"🚀 Starting Sandbox {self.container_name}...")
            
            container = self.client.containers.run(
                image=self.image,
                command=["python3", "script.py"],
                name=self.container_name,
                working_dir="/work",
                volumes={
                    self.host_work_dir: {'bind': '/work', 'mode': 'rw'}
                },
                network_mode="none",
                mem_limit="512m",
                read_only=True, # Root FS read-only
                detach=True,
                # fail-safe: kill after timeout + buffer
            )
            
            # 3. Wait for result with timeout
            try:
                result = container.wait(timeout=timeout_sec)
                exit_code = result['StatusCode']
            except Exception as e:
                logger.error(f"⏳ Sandbox Timeout ({timeout_sec}s): {e}")
                container.kill()
                return 124, "", f"TimeoutError: Execution exceeded {timeout_sec} seconds."

            # 4. Capture Output
            # Demux not reliably supported in all docker-py versions installed
            logs = container.logs(stdout=True, stderr=True)
            output = logs.decode("utf-8", errors="replace")
            
            # Return combined output as stdout, empty stderr for robustness
            stdout = output
            stderr = "" 

            return exit_code, stdout, stderr

        except docker.errors.ImageNotFound:
             logger.error(f"❌ Image {self.image} not found. Pulling...")
             self.client.images.pull(self.image)
             return self.run_code(code, timeout_sec) # Retry once
        except Exception as e:
            logger.error(f"❌ Sandbox Error: {e}")
            return 1, "", str(e)
            
        finally:
            # 5. Cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
