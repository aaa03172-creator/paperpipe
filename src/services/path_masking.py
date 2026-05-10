from pathlib import Path


def _is_falsey(raw: str) -> bool:
    return raw.strip().lower() in {"0", "false", "no", "off"}


def is_path_masking_enabled() -> bool:
    import os

    raw = (
        os.getenv("LATTICE_MASK_LOCAL_PATHS")
        or os.getenv("PAPERPIPE_MASK_LOCAL_PATHS")
    )
    if raw is None or not raw.strip():
        return True
    return not _is_falsey(raw)


def mask_local_path(raw_path: str | None) -> str | None:
    if raw_path is None:
        return None
    text = str(raw_path).strip()
    if not text:
        return raw_path

    path = Path(text).expanduser()
    if not path.is_absolute():
        return text

    cwd = Path.cwd().resolve()
    try:
        relative = path.resolve(strict=False).relative_to(cwd)
        return f"./{relative.as_posix()}"
    except Exception:
        name = path.name.strip()
        return f".../{name}" if name else ".../"
