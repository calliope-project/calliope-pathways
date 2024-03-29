"""List of lazy parsing scripts to convert files from Lombardi's study."""
import random

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from scipy.special import gamma
from yaml import safe_load

# >> Model setup >> User configurable
# Years
YEAR_STEP = 10
YEARS = np.arange(2020, 2050+YEAR_STEP, YEAR_STEP)
# Decommissioning (Randomized Weibull)
SEED = 5555
BETA_MIN = 3
BETA_MAX = 8
AGE_FACTOR_MIN = 0.1
AGE_FACTOR_MAX = 0.8
# Technologies with no growth
FROZEN_TECHS = ["geothermal", "battery_phs", "hydropower", "waste", "ccgt", "coal", "oil"]
# << Model setup <<

# >> Parsing setup >> DO NOT MODIFY!
BASIC_V07_COLS = ["nodes", "techs", "parameters", "values"]
INPUT_FILES = {
    "Calliope-Italy": {
        "locations": "https://raw.githubusercontent.com/FLomb/Calliope-Italy/master/italy_20_regions_v.0.2/Model/model_config/locations.yaml"
    },
    "stationary": {
        "techs": "src/calliope_pathways/models/italy_stationary/model_config/techs.yaml"
    }
}
OUTPUT_FILES = {
    "cap_initial": "src/calliope_pathways/models/italy_stationary/data_sources/initial_capacity_techs_kw.csv",
    "cap_max": "src/calliope_pathways/models/italy_stationary/data_sources/max_capacity_techs_kw.csv",
    "available_initial_cap": "src/calliope_pathways/models/italy_stationary/data_sources/investstep_series/available_initial_cap_techs.csv",
    "available_vintage_cap": "src/calliope_pathways/models/italy_stationary/data_sources/investstep_series/available_vintages_techs.csv"
}
# Technology aggregation
TECH_GROUPING = {
    "ccgt": ["ccgt"],
    "hydropower": ["hydro_dam", "hydro_ror"],
    "wind": ["wind"],
    "pv": ["pv_farm", "pv_rooftop"],
    "battery_phs": ["phs"],
    "waste": ["wte"],
    "bioenergy": ["biomass_wood", "biogas", "biofuel"],
    "oil": ["oil_&_other"],
    "geothermal": ["geothermal"],
    "coal": ["coal", "coal_usc"],
}
# Spatial aggregation
NODE_GROUPING = {
    "NORD": [f"R{i}" for i in range(1, 9)],
    "CNOR": [f"R{i}" for i in range(9, 12)],
    "CSUD": [f"R{i}" for i in range(12, 15)],
    "SUD": [f"R{i}" for i in range(15, 19)],
    "SICI": [],
    "SARD": [],
}
NODE_GROUPING = {k: [k] + i for k, i in NODE_GROUPING.items()}
# Parameter conversion
PARAM_V068_TO_V07 = {
    "flow_cap_initial": ["energy_cap_equals", "energy_cap_max"],
    "storage_cap_initial": ["storage_cap_equals"],
}
PARAM_INI_TO_MAX = { # TODO: this should be converted from Lombardi's file instead
    "flow_cap_initial": "flow_cap_max",
    "storage_cap_initial": "storage_cap_max",
}
# << Parsing setup <<

def _location_yaml_to_df(yaml_data: dict, calliope_version: str = "0.6.8") -> pd.DataFrame:
    """Converts a location yaml into a searchable dataframe."""
    # Read yaml file
    if calliope_version == "0.6.8":
        yaml_df = pd.json_normalize(yaml_data["locations"])
        yaml_df = yaml_df.T.reset_index()
        yaml_df.columns = ["commands", "values"]

        # Arrange commands into something sensible
        command_split = [
            "nodes",
            "node attributes",
            "items",
            "item attributes",
            "parameters",
        ]
        yaml_df[command_split] = yaml_df["commands"].str.split(".", expand=True)
        yaml_df = yaml_df.drop(columns="commands")
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
    return yaml_df


def _build_tech_df(yml_path: str, calliope_version: str = "0.7") -> pd.DataFrame:
    """Converts a tech yaml into a searchable dataframe."""
    # Read yaml file
    with open(yml_path, "r") as file:
        yaml_data = safe_load(file)
    if calliope_version == "0.7":
        yaml_df = pd.json_normalize(yaml_data["techs"])
        yaml_df = yaml_df.T.reset_index()
        yaml_df.columns = ["commands", "values"]

        # Arrange commands into something sensible
        command_split = ["techs", "parameters"]
        yaml_df = yaml_df[~yaml_df["commands"].str.contains("cost")]
        yaml_df[command_split] = yaml_df["commands"].str.split(".", expand=True)
        yaml_df = yaml_df.drop(columns="commands")
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
    return yaml_df


def _weibull(year: int, lifetime: float, shape: float, year_shift: int = 0, zero_min: float=1e-3) -> float:
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
    wb = np.exp(-(((year + year_shift) / lifetime) ** shape) * gamma(1 + 1 / shape) ** shape)
    if wb < zero_min:
        wb = 0
    return wb


def __test_group_completion(col: pd.Series, group_dict: dict) -> bool:
    """Check if a group dictionary covers all the possible values of a column."""
    return sorted(col.unique()) == sorted([i for j in group_dict.values() for i in j])


def parse_initial_cap(loc_yml_path: str, calliope_version="0.6.8") -> pd.DataFrame:
    """Extract initial installed capacity (2015 values)."""
    loc_yml_data = safe_load(requests.get(loc_yml_path).text)
    loc_yaml_df = _location_yaml_to_df(loc_yml_data, calliope_version)

    # Find exclusively numeric teach params in each location
    loc_tech_df = loc_yaml_df[
        (loc_yaml_df["node attributes"] == "techs")
        & (loc_yaml_df["item attributes"] == "constraints")
        & (loc_yaml_df["parameters"] != "resource")
    ]

    # Run tests
    assert (
        pd.to_numeric(loc_tech_df["values"], errors="coerce").notnull().all()
    ), "Invalid numeric values"
    assert __test_group_completion(
        loc_tech_df["nodes"], NODE_GROUPING
    ), "Missing nodes in group"
    assert __test_group_completion(
        loc_tech_df["items"], TECH_GROUPING
    ), "Missing techs in group"
    assert __test_group_completion(
        loc_tech_df["parameters"], PARAM_V068_TO_V07
    ), "Missing parameters in group"

    # build initial capacity datafile
    ini_cap_df = pd.DataFrame(columns=BASIC_V07_COLS)

    for n, n_group in NODE_GROUPING.items():
        node_df = loc_tech_df[loc_tech_df["nodes"].isin(n_group)]
        for t, t_group in TECH_GROUPING.items():
            tech_df = node_df[node_df["items"].isin(t_group)]
            for p, p_group in PARAM_V068_TO_V07.items():
                param_df = tech_df[tech_df["parameters"].isin(p_group)]
                if not param_df.empty:
                    aggregated_data = pd.Series(
                        data=[n, t, p, param_df["values"].sum()], index=BASIC_V07_COLS
                    )
                    ini_cap_df.loc[len(ini_cap_df.index)] = aggregated_data

    return ini_cap_df


def parse_cap_max(ini_cap_csv_path: str, techs: list) -> pd.DataFrame:
    """Create a file with maximum installed technology capacities using initial capacities."""
    cap_df = pd.read_csv(ini_cap_csv_path)
    cap_df = cap_df[
        (cap_df["techs"].isin(techs)) & (cap_df["parameters"].isin(PARAM_INI_TO_MAX))
    ]
    cap_df["parameters"] = cap_df["parameters"].replace(PARAM_INI_TO_MAX)

    return cap_df


def parse_available_initial_cap(
    tech_yml_path: str, ini_cap_csv_path: str, years: list
) -> pd.DataFrame:
    """Applies a Weibull function to the initial capacity to decrease it realistically.

    Args:
        tech_yml_path (str): yaml file with technology data
        node_tech_path (str): specifying installed technology per region
        years (list): range of years modelled
        shape_factor (int, optional): Weibull . Defaults to 0.5.
    """
    # get technology lifetimes
    tech_df = _build_tech_df(tech_yml_path)
    tech_life_df = tech_df[tech_df["parameters"].isin(["lifetime"])].set_index("techs")

    # fetch available technologies per region
    ini_cap_df = pd.read_csv(ini_cap_csv_path)
    remaining_df = ini_cap_df[["nodes", "techs"]].copy()
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
        avg_remaining_life = tech_life_df.loc[tech, "values"] * life_factors[i]
        remaining_df.loc[i, years[0] :] = [
            _weibull(y - years[0], avg_remaining_life, shape_factors[i]) for y in years
        ]

    return remaining_df

def parse_available_vintages(tech_yml_path: str, years: list, option: str = "cut") -> pd.DataFrame:
    # Get tech lifetimes
    tech_df = _build_tech_df(tech_yml_path)
    tech_life_df = tech_df[tech_df["parameters"].isin(["lifetime"])].set_index("techs")

    year_pairs = [(v, y) for y in years for v in years if v >= y]
    columns = pd.MultiIndex.from_tuples(year_pairs, names=["vintagesteps", "investsteps"])

    vintages_df = pd.DataFrame(index=tech_life_df.index, columns=columns)

    match option:
        case "cut":  # binary elimination of capacity
            for t in vintages_df.index:
                for (v, y) in vintages_df.columns:
                    if tech_life_df.loc[t, "values"] > (v-y):
                        vintages_df.loc[t, (v,y)] = 1
                    else:
                        vintages_df.loc[t, (v,y)] = 0
        case "share": # accounts for capacity ending between investsteps
            # TODO: only works for constant spacing between investsteps, for now.
            for t in vintages_df.index:
                for (v, y) in vintages_df.columns:
                    lifetime = tech_life_df.loc[t, "values"]
                    if lifetime > (v-y):
                        vintages_df.loc[t, (v,y)] = 1
                    elif lifetime > (v-y) - YEAR_STEP:
                        vintages_df.loc[t, (v,y)] = (lifetime % YEAR_STEP)/YEAR_STEP
                    else:
                        vintages_df.loc[t, (v,y)] = 0
        case "weibull":
            raise ValueError("This option has not been implemented yet.")
        case _:
            raise ValueError("Invalid option specified.")

    # TODO: bug workarounds
    vintages_df.loc["demand_electricity"] = 1
    vintages_df.index.name = None
    return vintages_df


def main(test_figs=True):

    ini_cap = parse_initial_cap(INPUT_FILES["Calliope-Italy"]["locations"])
    ini_cap.to_csv(OUTPUT_FILES["cap_initial"], index=False)

    cap_max_df = parse_cap_max(OUTPUT_FILES["cap_initial"], FROZEN_TECHS)
    cap_max_df.to_csv(OUTPUT_FILES["cap_max"], index=False)

    avail_ini_cap_df = parse_available_initial_cap(
        INPUT_FILES["stationary"]["techs"], OUTPUT_FILES["cap_initial"], YEARS
    )
    avail_ini_cap_df.to_csv(OUTPUT_FILES["available_initial_cap"], index=False)

    avail_vint_df = parse_available_vintages(INPUT_FILES["stationary"]["techs"], YEARS, option="share")
    avail_vint_df.to_csv(OUTPUT_FILES["available_vintage_cap"])

    if test_figs:
        avail_ini_cap_df.loc[:, YEARS[0]:].T.plot(legend=False)
        plt.savefig("outputs/test.png")


if __name__ == "__main__":
    main()
