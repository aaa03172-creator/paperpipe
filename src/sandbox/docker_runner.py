from typing import Tuple


class DockerSandbox:
    def __init__(self, job_id: str, work_dir: str):
        self.job_id = job_id
        self.work_dir = work_dir

    def run_code(self, code: str, timeout_sec: int = 30) -> Tuple[int, str, str]:
        _ = code
        _ = timeout_sec
        return (0, "", "")
