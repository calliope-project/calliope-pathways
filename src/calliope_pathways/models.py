# Copyright (C) since 2013 Calliope contributors listed in AUTHORS.
# Licensed under the Apache 2.0 License (see LICENSE file).

# Copyright (C) since 2024 Calliope pathways contributors listed in AUTHORS.
# Licensed under the MIT License (see LICENSE file).

"""
Models that can be loaded directly into a session.
"""

import importlib
from pathlib import Path

from calliope import AttrDict
from calliope.model import Model
from calliope.util import schema

MODEL_DIR = Path(importlib.resources.files("calliope_pathways") / "models")
MATH_DIR = Path(importlib.resources.files("calliope_pathways") / "math")

new_schema = AttrDict.from_yaml(MATH_DIR / "new_param_schema.yaml")

for key, new_params in new_schema.items():
    schema.update_model_schema(key, new_params, allow_override=False)


def national_scale(*args, **kwargs):
    """Returns the built-in national-scale example model."""

    return Model(
        model_definition=MODEL_DIR / "national_scale" / "model.yaml", *args, **kwargs
    )
