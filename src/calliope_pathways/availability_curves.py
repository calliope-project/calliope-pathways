"""List of lazy parsing scripts to convert files from Lombardi's study."""

import importlib
import importlib.resources
import random
from math import gamma
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(importlib.resources.files("calliope_pathways"))
# TODO: this could be a yaml file + schema... although it may be too specific
# -> Model setup -> User configurable
# Decommissioning (Randomized Weibull)
SEED = 5555
BETA_MIN = 3
BETA_MAX = 8
AGE_FACTOR_MIN = 0.1
AGE_FACTOR_MAX = 0.8
# Technologies with no growth
FROZEN_TECHS = ["geothermal", "battery_phs", "hydropower", "waste"]
# <- Model setup <-

# -> Parsing setup -> DO NOT MODIFY!
OUTPUT_FILES = {
    "initial_tech_capacities": "initial_capacity_techs_kw.csv",
    "maximum_tech_capacities": "max_capacity_techs_kw.csv",
    "available_initial_cap_techs": "investstep_series/available_initial_cap_techs.csv",
    "vintage_availability_techs": "investstep_series/available_vintages_techs.csv",
    "vintage_availability_transmission": "investstep_series/available_vintages_transmission.csv",
    "investstep_resolution": "investstep_series/investstep_resolution.csv",
}
PARAM_INI_TO_MAX = {
    "flow_cap_initial": "flow_cap_max",
    "storage_cap_initial": "storage_cap_max",
}
# <- Parsing setup <-


def _weibull(
    year: int,
    lifetime: float,
    shape: float,
    year_shift: int = 0,
    zero_min: float = 1e-3,
) -> float:
    """A Weibull probability distribution, see 10.1186/s12544-020-00464-0.

    Args:
        year (int): year in technology's lifetime, starting at 0.
        lifetime (float): average lifetime of a technology.
        shape (float): shape factor (Beta). <1 infant mortality, 1 random, >1 intrinsic wear-out.
        year_shift (int, optional): x-axis shift. Defaults to 0.
        zero_min (float, optional): minimum value allowed before defaulting to zero. Defaults to 1-e3.

    Returns:
        float: share of surviving capacity at given year.
    """
    wb = np.exp(
        -(((year + year_shift) / lifetime) ** shape) * gamma(1 + 1 / shape) ** shape
    )
    if wb < zero_min:
        wb = 0
    return wb


def parse_cap_max(initial_caps: pd.DataFrame, techs: list) -> pd.DataFrame:
    """Create a file with maximum installed technology capacities using initial capacities."""
    initial_caps = initial_caps[
        (initial_caps["techs"].isin(techs))
        & (initial_caps["parameters"].isin(PARAM_INI_TO_MAX))
    ]
    initial_caps["parameters"] = initial_caps["parameters"].replace(PARAM_INI_TO_MAX)
    return initial_caps


def parse_available_initial_cap(
    tech_lifetimes: dict, initial_caps: pd.DataFrame, years: list
) -> pd.DataFrame:
    """Applies a Weibull function to the initial capacity to decrease it realistically.

    Args:
        tech_lifetimes (dict): Technology lifetimes.
        initial_caps (pd.DataFrame): Initial technology capacities
        years (list): range of years modelled
    """
    # fetch available technologies per region
    remaining_df = initial_caps[["nodes", "techs"]].copy()
    remaining_df = remaining_df.drop_duplicates(ignore_index=True)
    # Construct random phase-out sequence
    random.seed(SEED, version=2)
    shape_factors = [random.uniform(BETA_MIN, BETA_MAX) for _ in remaining_df.index]
    life_factors = [
        random.uniform(AGE_FACTOR_MIN, AGE_FACTOR_MAX) for _ in remaining_df.index
    ]
    # Get phase-out sequence using a Weibull function
    remaining_df[years] = 0.0

    for i in remaining_df.index:
        tech = remaining_df.loc[i, "techs"]
        avg_remaining_life = tech_lifetimes[tech] * life_factors[i]
        remaining_df.loc[i, years[0] :] = [
            _weibull(y - years[0], avg_remaining_life, shape_factors[i]) for y in years
        ]

    return remaining_df


def parse_available_vintages(
    tech_lifetimes: dict[str, int], years: list, year_step: int, option: str = "cut"
) -> pd.DataFrame:
    """Parse available vintages table.

    This gives fractional values of each vintage's availability in each investstep.

    Args:
        tech_lifetimes (dict[str, int]): Technology lifetimes.
        years (list): range of years modelled.
        year_step (int): Years between investsteps.
        option (str, optional): Method for creating vintage availability curves. Defaults to "cut".

    Raises:
        ValueError: _description_
        ValueError: _description_

    Returns:
        pd.DataFrame: Vintage availability table.
    """
    year_pairs = [(v, y) for y in years for v in years if v >= y]
    columns = pd.MultiIndex.from_tuples(
        year_pairs, names=["investsteps", "vintagesteps"]
    )

    vintages_df = pd.DataFrame(index=tech_lifetimes.keys(), columns=columns)

    match option:
        case "cut":  # binary elimination of capacity
            for t in vintages_df.index:
                for v, y in vintages_df.columns:
                    if tech_lifetimes[t] > (v - y):
                        vintages_df.loc[t, (v, y)] = 1
                    else:
                        vintages_df.loc[t, (v, y)] = 0
        case "share":  # accounts for capacity ending between investsteps
            # TODO: only works for constant spacing between investsteps, for now.
            for t in vintages_df.index:
                for v, y in vintages_df.columns:
                    lifetime = tech_lifetimes[t]
                    if lifetime > (v - y):
                        vintages_df.loc[t, (v, y)] = 1
                    elif lifetime > (v - y) - year_step:
                        vintages_df.loc[t, (v, y)] = (lifetime % year_step) / year_step
                    else:
                        vintages_df.loc[t, (v, y)] = 0
        case "weibull":
            raise ValueError("This option has not been implemented yet.")
        case _:
            raise ValueError("Invalid option specified.")

    # TODO: bug workarounds
    vintages_df.index.name = None
    return vintages_df


def parse_transmission(techs: list[str], years: list) -> pd.DataFrame:
    """Parse transmission technology vintage availability, assuming indefinite availability.

    Args:
        techs (list[str]): Transmission techs
        years (list): Range of years modelled.

    Returns:
        pd.DataFrame: Transmission technology vintage availability.
    """
    year_pairs = [(v, y) for y in years for v in years if v >= y]
    columns = pd.MultiIndex.from_tuples(
        year_pairs, names=["investsteps", "vintagesteps"]
    )
    return pd.DataFrame(index=techs, columns=columns, data=1)


def parse_investstep_resolution(years: list) -> pd.DataFrame:
    """Create an investstep resolution table."""
    year_df = pd.Series(index=years, data=years).diff().bfill().astype(int)
    return year_df.rename_axis(index="investsteps").to_frame("investstep_resolution")


def _get_years(first_year: int, final_year: int, investstep_resolution: int) -> list:
    if (final_year - first_year) % investstep_resolution != 0:
        raise ValueError(
            "Investment resolution must fit between first and final year without any partial investment periods."
        )
    return list(
        range(first_year, final_year + investstep_resolution, investstep_resolution)
    )


def _save_str(path: Path, relative_to: str | Path, absolute: bool = False) -> str:
    if absolute:
        return str(path.absolute())
    else:
        return str(path.relative_to(relative_to))


def parse(
    model_dir: str | Path,
    initial_capacities_kw: pd.DataFrame,
    tech_lifetimes: dict[str, int],
    frozen_techs: list[str] | None = None,
    transmission_techs: list[str] | None = None,
    first_year: int = 2025,
    final_year: int = 2050,
    investstep_resolution: int = 5,
    absolute_paths: bool = False,
) -> dict[str, dict]:
    """Generate data tables to convert an end-state model into a pathways-compatible model.

    Args:
        model_dir (str | Path): Directory in which the `model.yaml` is stored.
        initial_capacities_kw (pd.DataFrame): A table of initial capacities indexed by [`nodes`, `techs`, `parameters`, `values`]
        tech_lifetimes (dict[str, int]): Model technology lifetimes
        frozen_techs (list[str] | None, optional): Any given technologies will be forced to their initial capacities in all investment periods (no growth allowed). Defaults to None.
        transmission_techs (list[str] | None, optional): List of model transmission technologies. Defaults to None.
        first_year (int, optional): First investment year of the pathway optimisation. Defaults to 2025.
        final_year (int, optional): Final investment year of the pathway optimisation. Defaults to 2050.
        investstep_resolution (int, optional): Steps between pathway investment periods. Defaults to 5.
        absolute_paths (bool, optional): If True, the data table YAML will contain absolute paths. If False, paths will be relative to the model directory. Defaults to False.

    Returns:
        dict[str, dict]: Calliope-compatible data table list.
            It can be used when scripting using `override_dict` or can be saved to YAML and imported in your `model.yaml`.
    """
    data_dir = Path(model_dir) / "data_tables"
    series_dir = data_dir / "investstep_series"
    series_dir.mkdir(exist_ok=True, parents=True)
    data_table_yamls: dict[str, dict] = dict()
    years = _get_years(first_year, final_year, investstep_resolution)

    initial_capacities_kw.to_csv(
        data_dir / "initial_capacity_techs_kw.csv", index=False
    )
    data_table_yamls["initial_tech_capacities"] = {
        "data": _save_str(
            data_dir / "initial_capacity_techs_kw.csv", model_dir, absolute_paths
        ),
        "rows": ["nodes", "techs", "parameters"],
        "columns": ["values"],
        "drop": "values",
    }

    if frozen_techs:
        cap_max_df = parse_cap_max(initial_capacities_kw, frozen_techs)
        cap_max_df.to_csv(data_dir / "max_capacity_techs_kw.csv", index=False)

        data_table_yamls["maximum_tech_capacities"] = {
            "data": _save_str(
                data_dir / "max_capacity_techs_kw.csv", model_dir, absolute_paths
            ),
            "rows": ["nodes", "techs", "parameters"],
            "columns": ["values"],
            "drop": "values",
        }

    avail_ini_cap_df = parse_available_initial_cap(
        tech_lifetimes, initial_capacities_kw, years
    )
    avail_ini_cap_df.to_csv(series_dir / "available_initial_cap_techs.csv", index=False)
    data_table_yamls["available_initial_cap_techs"] = {
        "data": _save_str(
            series_dir / "available_initial_cap_techs.csv", model_dir, absolute_paths
        ),
        "rows": ["nodes", "techs"],
        "columns": "investsteps",
        "add_dims": {"parameters": "available_initial_cap"},
    }

    avail_vint_df = parse_available_vintages(
        tech_lifetimes, years, year_step=investstep_resolution, option="share"
    )
    avail_vint_df.to_csv(series_dir / "available_vintages_techs.csv")
    data_table_yamls["vintage_availability_techs"] = {
        "data": _save_str(
            series_dir / "available_vintages_techs.csv", model_dir, absolute_paths
        ),
        "rows": "techs",
        "columns": ["investsteps", "vintagesteps"],
        "add_dims": {"parameters": "available_vintages"},
    }

    if transmission_techs:
        avail_vint_trans_df = parse_transmission(transmission_techs, years)
        avail_vint_trans_df.to_csv(series_dir / "available_vintages_transmission.csv")
        data_table_yamls["vintage_availability_transmission"] = {
            "data": _save_str(
                series_dir / "available_vintages_transmission.csv",
                model_dir,
                absolute_paths,
            ),
            "rows": "techs",
            "columns": ["investsteps", "vintagesteps"],
            "add_dims": {"parameters": "available_vintages"},
        }

    investstep_res_df = parse_investstep_resolution(years)
    investstep_res_df.to_csv(series_dir / "investstep_resolution.csv")
    data_table_yamls["investstep_resolution"] = {
        "data": _save_str(
            series_dir / "investstep_resolution.csv", model_dir, absolute_paths
        ),
        "rows": "investsteps",
        "columns": "parameters",
    }
    return data_table_yamls
