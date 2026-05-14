import docker

from src.sandbox.docker_runner import DockerSandbox


class _FakeImages:
    def __init__(self, exists: bool):
        self.exists = exists
        self.built = False
        self.build_kwargs = None

    def get(self, _name: str):
        if self.exists:
            return object()
        raise docker.errors.ImageNotFound("missing")

    def build(self, **kwargs):
        self.built = True
        self.build_kwargs = kwargs
        return object(), [{"stream": "ok"}]


class _FakeClient:
    def __init__(self, exists: bool):
        self.images = _FakeImages(exists=exists)


def test_build_dockerfile_contains_stats_dependencies(monkeypatch):
    fake = _FakeClient(exists=True)
    monkeypatch.setattr("src.sandbox.docker_runner.docker.from_env", lambda: fake)

    sandbox = DockerSandbox(job_id="job1", work_dir="/tmp/paperpipe-sandbox")
    dockerfile = sandbox._build_dockerfile()

    assert "FROM" in dockerfile
    assert "pip install" in dockerfile
    assert "pandas" in dockerfile
    assert "scipy" in dockerfile
    assert "statsmodels" in dockerfile


def test_ensure_image_builds_when_missing(monkeypatch):
    fake = _FakeClient(exists=False)
    monkeypatch.setattr("src.sandbox.docker_runner.docker.from_env", lambda: fake)

    sandbox = DockerSandbox(job_id="job2", work_dir="/tmp/paperpipe-sandbox")
    sandbox._ensure_image()

    assert fake.images.built is True
    assert fake.images.build_kwargs is not None
    assert fake.images.build_kwargs["tag"] == sandbox.image
