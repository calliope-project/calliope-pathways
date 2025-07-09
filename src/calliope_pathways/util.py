"""Utility functions."""

import importlib.resources
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry
from calliope import io, util

_SRC_DIR = importlib.resources.files("calliope_pathways")

BASIC_V07_COLS = ["nodes", "techs", "parameters", "values"]


def src_dir_ref(dir: str | Path) -> Path:
    """Get directory path within the calliope_pathways package.

    Args:
        dir (str | Path): `calliope_pathways` subdirectory.

    Returns:
        Path: pathlike object to `dir`.
    """
    with importlib.resources.as_file(_SRC_DIR) as f:
        return f / dir


def reset_schema():
    """Reset the calliope schema."""
    util.schema.reset()

    new_schema = io.read_rich_yaml(src_dir_ref("config") / "new_param_schema.yaml")

    for key, new_params in new_schema.items():
        util.schema.update_model_schema(key, new_params, allow_override=False)


def transform_series(
    series: pd.Series, grouping: dict, dtype: str = "string"
) -> pd.Series:
    """Use a grouping dictionary to transform a pandas Series.

    Groupings are defined as {new_name:[old_name, ..., other_oldname],...}.

    Args:
        series (pd.Series): dataframe with the column to transform.
        grouping (dict): grouping to use for the transformation.
        dtype (str, optional): dtype to set for the new data series. Defaults to "string".

    Raises:
        ValueError: grouping was not exhaustive (not all original values covered).

    Returns:
        pd.Series: transformed data series.
    """
    transformed = pd.Series(np.nan, index=series.index, dtype=dtype)

    for new, old_group in grouping.items():
        transformed.loc[series.isin(old_group)] = new
    if any(pd.isna(transformed)):
        raise ValueError(f"Missing values while transforming {series}.")
    return transformed


def convert_country(
    countries: list[str], code_from: str = "name", code_to: str = "alpha_2"
):
    """Convert all listed countries from given name/code into requested name/code."""
    countries_converted = []
    for country in countries:
        country_data = pycountry.countries.get(**{code_from: country})
        if country_data is None:
            country_data = pycountry.countries.search_fuzzy(country)[0]
        countries_converted.append(getattr(country_data, code_to))
    return countries_converted


def get_lifetimes(yml_path: str, calliope_version: str = "0.7") -> dict:
    """Extracts tech lifetimes from the tech YAML."""
    # Read yaml file
    yaml_data = io.read_rich_yaml(yml_path)
    if calliope_version == "0.7":
        return {
            k.split(".")[0]: v
            for k, v in yaml_data["techs"].as_dict_flat().items()
            if k.endswith(".lifetime")
        }
    else:
        raise ValueError(f"Version {calliope_version} not supported.")


def get_base_tech(yml_path: str, calliope_version: str = "0.7") -> dict:
    """Extracts tech lifetimes from the tech YAML."""
    # Read yaml file
    yaml_data = io.read_rich_yaml(yml_path)
    if calliope_version == "0.7":
        return {
            k.split(".")[0]: v
            for k, v in yaml_data["techs"].as_dict_flat().items()
            if k.endswith(".base_tech")
        }
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
