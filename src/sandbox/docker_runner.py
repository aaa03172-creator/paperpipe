import docker
import os
import tarfile
import io
import logging
from typing import Tuple

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
        self.base_image = os.getenv("PAPERPIPE_SANDBOX_BASE_IMAGE", "python:3.10-slim")
        self.image = os.getenv("PAPERPIPE_SANDBOX_IMAGE", "paperpipe-sandbox:py310-stats-v1")
        self.required_packages = [
            "numpy==2.1.3",
            "pandas==2.2.3",
            "scipy==1.14.1",
            "statsmodels==0.14.4",
        ]
        
        # Ensure host work dir exists
        os.makedirs(self.host_work_dir, exist_ok=True)

    def _build_dockerfile(self) -> str:
        pkg_line = " ".join(self.required_packages)
        return (
            f"FROM {self.base_image}\n"
            "ENV PYTHONDONTWRITEBYTECODE=1\n"
            "ENV PYTHONUNBUFFERED=1\n"
            "WORKDIR /work\n"
            f"RUN pip install --no-cache-dir {pkg_line}\n"
        )

    def _ensure_image(self) -> None:
        try:
            self.client.images.get(self.image)
            return
        except docker.errors.ImageNotFound:
            logger.info("Sandbox image not found (%s). Building with stats dependencies...", self.image)
        except Exception as e:
            logger.warning("Unable to inspect sandbox image %s: %s", self.image, e)

        dockerfile = self._build_dockerfile().encode("utf-8")
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            info = tarfile.TarInfo(name="Dockerfile")
            info.size = len(dockerfile)
            tar.addfile(tarinfo=info, fileobj=io.BytesIO(dockerfile))
        tar_stream.seek(0)
        self.client.images.build(
            fileobj=tar_stream,
            custom_context=True,
            rm=True,
            tag=self.image,
            pull=False,
        )
        logger.info("Sandbox image ready: %s", self.image)

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
            self._ensure_image()

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
                tmpfs={"/tmp": "rw,nosuid,nodev,size=64m"},
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
