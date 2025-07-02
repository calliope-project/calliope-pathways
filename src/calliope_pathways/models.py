# Copyright (C) since 2013 Calliope contributors listed in AUTHORS.
# Licensed under the Apache 2.0 License (see LICENSE file).

# Copyright (C) since 2024 Calliope pathways contributors listed in AUTHORS.
# Licensed under the MIT License (see LICENSE file).

"""Models that can be loaded directly into a session."""

import tempfile
from pathlib import Path

from calliope import attrdict, io
from calliope.model import Model
from calliope.util import schema

from calliope_pathways.model_configs import parse_lombardi
from calliope_pathways.util import src_dir_ref

new_schema = io.read_rich_yaml(src_dir_ref("config") / "new_param_schema.yaml")

for key, new_params in new_schema.items():
    schema.update_model_schema(key, new_params, allow_override=False)


def national_scale(**kwargs) -> Model:
    """Returns the built-in national-scale example model."""
    return Model(
        model_definition=src_dir_ref("model_configs") / "national_scale" / "model.yaml",
        **kwargs,
    )


def italy(
    first_year: int = 2025,
    final_year: int = 2050,
    investstep_resolution: int = 5,
    **kwargs,
) -> Model:
    """Returns stationary test-case for Italy.

    Args:
        first_year (int, optional): First year of investment horizon (inclusive). Defaults to 2025.
        final_year (int, optional): Final year of investment horizon (inclusive). Defaults to 2050.
        investstep_resolution (int, optional): Year increment between investment periods. Defaults to 5.
        **kwargs: Passed on to `calliope.Model(...)`.

    Returns:
        Model: Initialised Italy Calliope Model.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_dir = src_dir_ref("model_configs") / "italy"
        data_source_overrides = parse_lombardi.main(
            first_year,
            final_year,
            investstep_resolution,
            data_dir=tmp_dir,
            model_dir=model_dir,
        )
        override_dict = {
            **{"data_tables": data_source_overrides},
            **kwargs.pop("override_dict", {}),
        }
        return Model(
            model_definition=model_dir / "model.yaml",
            override_dict=override_dict,
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
        **kwargs: calliope `init` config kwargs.

    Keyword Args: Passed on to `calliope.Model`.
    """
    kwargs = attrdict.AttrDict(kwargs)
    existing_add_math = kwargs.get_key("override_dict.config.build.add_math", [])
    if add_pathways_math:
        existing_add_math.append(
            str((src_dir_ref("math") / "pathways.yaml").absolute())
        )
    kwargs.set_key("override_dict.config.build.add_math", existing_add_math)
    model = Model(model_definition=model_definition, **kwargs)

    return model
