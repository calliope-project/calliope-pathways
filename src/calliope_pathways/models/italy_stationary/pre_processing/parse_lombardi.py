"""List of lazy parsing scripts to convert files from Lombardi's study."""
import random

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.special import gamma
from yaml import safe_load

# Weibull settings
SEED = 7000
BETA_MIN = 3
BETA_MAX = 8
AGE_FACTOR_MIN = 0.1
AGE_FACTOR_MAX = 0.8

NODE_GROUPING = {
    "NORD": [f"R{i}" for i in range(1, 9)],
    "CNOR": [f"R{i}" for i in range(9, 12)],
    "CSUD": [f"R{i}" for i in range(12, 15)],
    "SUD": [f"R{i}" for i in range(15, 19)],
    "SICI": [],
    "SARD": [],
}

NODE_GROUPING = {k: [k] + i for k, i in NODE_GROUPING.items()}

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

PARAM_V068_TO_V07 = {
    "initial_flow_cap": ["energy_cap_equals", "energy_cap_max"],
    "initial_storage_cap": ["storage_cap_equals"],
}

PARAM_INI_TO_MAX = {
    "initial_flow_cap": "flow_cap_max",
    "initial_storage_cap": "storage_cap_max"
}

BASIC_V07_COLS = ["nodes", "techs", "parameters", "values"]


def _location_yaml_to_df(path: str, calliope_version: str="0.6.8") -> pd.DataFrame:
    """Converts a location yaml into a searchable dataframe."""
    # Read yaml file
    with open(path, "r") as file:
        yaml_data = safe_load(file)
    if calliope_version == "0.6.8":
        yaml_df = pd.json_normalize(yaml_data["locations"])
        yaml_df = yaml_df.T.reset_index()
        yaml_df.columns = ["commands", "value"]

        # Arrange commands into something sensible
        command_split = ["nodes", "node attributes", "items", "item attributes", "parameters"]
        yaml_df[command_split] = yaml_df["commands"].str.split(".", expand=True)
        yaml_df = yaml_df.drop(columns="commands")
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
    return yaml_df

def _build_tech_df(yml_path: str, calliope_version: str="0.7") -> pd.DataFrame:
    """Converts a tech yaml into a searchable dataframe."""
    # Read yaml file
    with open(yml_path, "r") as file:
        yaml_data = safe_load(file)
    if calliope_version == "0.7":
        yaml_df = pd.json_normalize(yaml_data["techs"])
        yaml_df = yaml_df.T.reset_index()
        yaml_df.columns = ["commands", "value"]

        # Arrange commands into something sensible
        command_split = ["techs", "parameters"]
        yaml_df = yaml_df[~yaml_df["commands"].str.contains("cost")]
        yaml_df[command_split] = yaml_df["commands"].str.split(".", expand=True)
        yaml_df = yaml_df.drop(columns="commands")
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
    return yaml_df

def _weibull(year: int, lifetime: float, shape: float, year_shift: int=0) -> float:
    """A Weibull probability distribution, see 10.1186/s12544-020-00464-0."""
    return np.exp(-(((year+year_shift)/lifetime)**shape) * gamma(1+1/shape)**shape)

def __test_group_completion(col: pd.Series, group_dict: dict) -> bool:
    """Check if a group dictionary covers all the possible values of a column."""
    return sorted(col.unique()) == sorted([i for j in group_dict.values() for i in j])

# def get_techs_per_node(input_yaml_path: str) -> dict:
#     """Get a dictionary specifying the technologies installed in a given region.

#     Args:
#         input_path (str): path to Lombardi's location.yaml

#     Returns:
#         dict: containing {node: [techs]}
#     """
#     loc_yaml_df = _location_yaml_to_df(input_yaml_path)
#     loc_tech_df = loc_yaml_df[loc_yaml_df["node attributes"] == "techs"]

#     replace_dict = {v: k for k, values in TECH_GROUPING.items() for v in values}
#     loc_tech_df["items"] = loc_tech_df["items"].replace(replace_dict)

#     return {n: loc_tech_df[loc_tech_df["nodes"].isin(n_group)]["items"].unique() for n, n_group in NODE_GROUPING.items()}

def parse_initial_cap(loc_yml_path: str, calliope_version="0.6.8") -> pd.DataFrame:
    """Extract initial installed capacity (2015 values)."""
    loc_yaml_df = _location_yaml_to_df(loc_yml_path, calliope_version)

    # Find exclusively numeric teach params in each location
    loc_tech_df = loc_yaml_df[
        (loc_yaml_df["node attributes"] == "techs")
        & (loc_yaml_df["item attributes"] == "constraints")
        & (loc_yaml_df["parameters"] != "resource")
    ]

    # Run tests
    assert pd.to_numeric(loc_tech_df["value"], errors="coerce").notnull().all(), "Invalid numeric values"
    assert __test_group_completion(loc_tech_df["nodes"], NODE_GROUPING), "Missing nodes in group"
    assert __test_group_completion(loc_tech_df["items"], TECH_GROUPING), "Missing techs in group"
    assert __test_group_completion(loc_tech_df["parameters"], PARAM_V068_TO_V07), "Missing parameters in group"

    # build initial capacity datafile
    ini_cap_df = pd.DataFrame(columns=BASIC_V07_COLS)

    for n, n_group in NODE_GROUPING.items():
        node_df = loc_tech_df[loc_tech_df["nodes"].isin(n_group)]
        for t, t_group in TECH_GROUPING.items():
            tech_df = node_df[node_df["items"].isin(t_group)]
            for p, p_group in PARAM_V068_TO_V07.items():
                param_df = tech_df[tech_df["parameters"].isin(p_group)]
                if not param_df.empty:
                    aggregated_data = pd.Series(data=[n, t, p, param_df["value"].sum()], index=BASIC_V07_COLS)
                    ini_cap_df.loc[len(ini_cap_df.index)] = aggregated_data

    return ini_cap_df

def parse_cap_max(ini_cap_csv_path: str, techs: list) -> pd.DataFrame:
    """Create a file with maximum installed technology capacities using initial capacities."""
    cap_df = pd.read_csv(ini_cap_csv_path)

    # assert __test_group_completion(cap_df["parameters"], PARAM_INI_TO_MAX), "Missing parameters in group"

    cap_df = cap_df[(cap_df["techs"].isin(techs)) & (cap_df["parameters"].isin(PARAM_INI_TO_MAX))]
    cap_df["parameters"] = cap_df["parameters"].replace(PARAM_INI_TO_MAX)

    # for t in techs:
    #     tech_df = ini_cap_df[(ini_cap_df["techs"] == t) & (ini_cap_df["parameters"].isin(PARAM_INI_TO_MAX))].copy()
    #     if not tech_df.empty:
    #         tech_df["parameters"] = tech_df["parameters"].replace(PARAM_INI_TO_MAX)
    #         cap_max_df = pd.concat([cap_max_df, tech_df])

    return cap_df


def parse_cap_remaining(tech_yml_path: str, ini_cap_csv_path: str, years: list) -> pd.DataFrame:
    """Applies a Weibull function to the initial capacity to decrease it realistically.

    Args:
        tech_yml_path (str): yaml file with technology data
        node_tech_path (str): specifying installed technology per region
        years (list): range of years modelled
        shape_factor (int, optional): Weibull . Defaults to 0.5.
    """
    # technology lifetime
    tech_df = _build_tech_df(tech_yml_path)
    tech_life_df = tech_df[tech_df["parameters"].isin(["lifetime"])].set_index("techs")

    # fetch available technologies per region
    ini_cap_df = pd.read_csv(ini_cap_csv_path)
    remaining_df = ini_cap_df[["nodes", "techs"]].copy()

    # Construct random phase-out sequence
    random.seed(SEED, version=2)
    shape_factors = [random.uniform(BETA_MIN, BETA_MAX) for _ in remaining_df.index]
    life_factors = [random.uniform(AGE_FACTOR_MIN, AGE_FACTOR_MAX) for _ in remaining_df.index]

    # Get phase-out sequence using a Weibull function
    remaining_df[years] = 0.0

    for i in remaining_df.index:
        tech = remaining_df.loc[i, "techs"]
        avg_remaining_life = tech_life_df.loc[tech, "value"] * life_factors[i]
        remaining_df.loc[i, years[0]:] = [_weibull(y-years[0], avg_remaining_life, shape_factors[i]) for y in years]

    return remaining_df


def main(test_figs=False):
    loc_lombardi_yml = "src/calliope_pathways/models/italy_stationary/pre_processing/locations_lombardi.yaml"
    tech_stationary_yml = "src/calliope_pathways/models/italy_stationary/model_config/techs.yaml"

    ini_cap = parse_initial_cap(loc_lombardi_yml)
    ini_cap_path = "src/calliope_pathways/models/italy_stationary/data_sources/inital_capacity_techs_kw.csv"
    ini_cap.to_csv(ini_cap_path, index=False)

    cap_max_df = parse_cap_max(ini_cap_path, ["geothermal", "battery_phs", "hydropower", "waste"])
    frozen_path = "src/calliope_pathways/models/italy_stationary/data_sources/max_capacity_techs_kw.csv"
    cap_max_df.to_csv(frozen_path, index=False)

    years = np.arange(2020,2060,10)
    avail_ini_cap_df = parse_cap_remaining(tech_stationary_yml, ini_cap_path,years)
    avail_ini_path = "src/calliope_pathways/models/italy_stationary/data_sources/investstep_series/available_initial_cap.csv"
    avail_ini_cap_df.to_csv(avail_ini_path, index=False)

    if test_figs:
        avail_ini_cap_df.loc[:, 2020:].T.plot()
        plt.savefig("test.png")



if __name__ == "__main__":
    main()
