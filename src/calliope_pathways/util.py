import importlib.resources
from pathlib import Path

from calliope import AttrDict, util

_SRC_DIR = importlib.resources.files("calliope_pathways")


def src_dir_ref(dir: str | Path) -> Path:
    with importlib.resources.as_file(_SRC_DIR) as f:
        return f / dir


def reset_schema():
    util.schema.reset()

    new_schema = AttrDict.from_yaml(src_dir_ref("config") / "new_param_schema.yaml")

    for key, new_params in new_schema.items():
        util.schema.update_model_schema(key, new_params, allow_override=False)
