# Copyright (C) since 2013 Calliope contributors listed in AUTHORS.
# Licensed under the Apache 2.0 License (see LICENSE file).

# Copyright (C) since 2024 Calliope pathways contributors listed in AUTHORS.
# Licensed under the MIT License (see LICENSE file).

"""
Models that can be loaded directly into a session.
"""

from pathlib import Path

from calliope import AttrDict
from calliope.model import Model
from calliope.util import schema

from calliope_pathways.util import src_dir_ref

new_schema = AttrDict.from_yaml(src_dir_ref("config") / "new_param_schema.yaml")

for key, new_params in new_schema.items():
    schema.update_model_schema(key, new_params, allow_override=False)


def national_scale(**kwargs) -> Model:
    """Returns the built-in national-scale example model."""

    return Model(
        model_definition=src_dir_ref("models") / "national_scale" / "model.yaml",
        **kwargs,
    )


def load(
    model_definition: str | Path, add_pathways_math: bool = True, **kwargs
) -> Model:
    """Load a user-defined model, adding calliope_pathways math if desired.

    Args:
        model_definition (str | Path): Path to user's `model.yaml` file.
        add_pathways_math (bool, optional):
            If True, the model math will be updated with pre-defined `calliope_pathways` math.
            Set to False if you already have a reference to the math file in your `init.add_math` configuration.
            Defaults to True.

    Keyword Args: Passed on to `calliope.Model`.
    """

    model = Model(model_definition=model_definition, **kwargs)
    if add_pathways_math:
        math = AttrDict.from_yaml(src_dir_ref("math") / "pathways.yaml")
        model.math.union(math, allow_override=True)
    return model
