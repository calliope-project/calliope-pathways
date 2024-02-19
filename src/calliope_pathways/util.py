import importlib.resources
from pathlib import Path

_SRC_DIR = importlib.resources.files("calliope_pathways")


def src_dir_ref(dir: str | Path) -> Path:
    with importlib.resources.as_file(_SRC_DIR) as f:
        return f / dir
