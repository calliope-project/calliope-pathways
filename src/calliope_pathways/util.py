import importlib.resources
from pathlib import Path
import numpy as np
from calliope import AttrDict, util
import pandas as pd
import pycountry
_SRC_DIR = importlib.resources.files("calliope_pathways")

BASIC_V07_COLS = ["nodes", "techs", "parameters", "values"]

def src_dir_ref(dir: str | Path) -> Path:
    with importlib.resources.as_file(_SRC_DIR) as f:
        return f / dir


def reset_schema():
    util.schema.reset()

    new_schema = AttrDict.from_yaml(src_dir_ref("config") / "new_param_schema.yaml")

    for key, new_params in new_schema.items():
        util.schema.update_model_schema(key, new_params, allow_override=False)

def transform_series(series: pd.Series, grouping: dict, dtype="string") -> pd.Series:
    """Use a grouping dictionary to transform a pandas Series.

    Groupings are defined as {new_name:[old_name, ..., other_oldname],...}.

    Args:
        df (pd.Series): dataframe with the column to transform.
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

def convert_country(countries: list[str], code_from: str = "name", code_to: str = "alpha_2"):
    countries_converted = []
    for country in countries:
        country_data = pycountry.countries.get(**{code_from: country})
        if country_data is None:
            country_data = pycountry.countries.search_fuzzy(country)[0]
        countries_converted.append(getattr(country_data, code_to))
    return countries_converted
