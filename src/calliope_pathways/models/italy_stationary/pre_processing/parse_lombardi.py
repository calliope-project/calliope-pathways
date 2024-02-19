"""List of lazy parsing scripts to convert files from Lombardi's study."""
import pandas as pd
from yaml import safe_load

NODE_GROUPS = {
    "NORD": [f"R{i}" for i in range(1, 9)],
    "CNOR": [f"R{i}" for i in range(9, 12)],
    "CSUD": [f"R{i}" for i in range(12, 15)],
    "SUD": [f"R{i}" for i in range(15, 19)],
    "SICI": [],
    "SARD": [],
}

NODE_GROUPS = {k: [k] + i for k, i in NODE_GROUPS.items()}

TECH_GROUPS = {
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

PARAM_GROUPS = {
    "initial_flow_cap": ["energy_cap_equals", "energy_cap_max"],
    "initial_storage_cap": ["storage_cap_equals"],
}

FREEZE_CONVERT = {
    "initial_flow_cap": "flow_cap_max",
    "initial_storage_cap": "storage_cap_max"
}

CALLIOPE_COLS = ["nodes", "techs", "parameters", "values"]


def _build_location_df(path: str) -> pd.DataFrame:
    # Read yaml file
    with open(path, "r") as file:
        yaml_data = safe_load(file)
    yaml_df = pd.json_normalize(yaml_data["locations"])
    yaml_df = yaml_df.T.reset_index()
    yaml_df.columns = ["command", "value"]

    # Arrange commands into something sensible
    command_split = ["node", "node attribute", "item", "item attribute", "parameter"]
    yaml_df[command_split] = yaml_df["command"].str.split(".", expand=True)
    yaml_df = yaml_df.drop(columns="command")
    return yaml_df


def _test_group_completion(col: pd.Series, group_dict: dict) -> bool:
    """Check if a group dictionary covers all the possible values of a column."""
    return sorted(col.unique()) == sorted([i for j in group_dict.values() for i in j])


def parse_initial_cap(input_yaml_path: str, csv_out_path: str) -> None:
    """Extract initial installed capacity (2015 values)."""
    yaml_df = _build_location_df(input_yaml_path)

    # Build a dataframe with numeric tech parameters
    tech_old_df = yaml_df[
        (yaml_df["node attribute"] == "techs")
        & (yaml_df["item attribute"] == "constraints")
        & (yaml_df["parameter"] != "resource")
    ]

    # Run tests
    assert pd.to_numeric(tech_old_df["value"], errors="coerce").notnull().all(), "Invalid numeric values"
    assert _test_group_completion(tech_old_df["node"], NODE_GROUPS), "Missing nodes in group"
    assert _test_group_completion(tech_old_df["item"], TECH_GROUPS), "Missing techs in group"
    assert _test_group_completion(tech_old_df["parameter"], PARAM_GROUPS), "Missing parameters in group"

    # build initial capacity datafile
    initial_cap_df = pd.DataFrame(columns=CALLIOPE_COLS)

    for n, n_group in NODE_GROUPS.items():
        node_df = tech_old_df[tech_old_df["node"].isin(n_group)]
        for t, t_group in TECH_GROUPS.items():
            tech_df = node_df[node_df["item"].isin(t_group)]
            for p, p_group in PARAM_GROUPS.items():
                param_df = tech_df[tech_df["parameter"].isin(p_group)]
                if not param_df.empty:
                    aggregated_data = pd.Series(data=[n, t, p, param_df["value"].sum()], index=CALLIOPE_COLS)
                    initial_cap_df.loc[len(initial_cap_df.index)] = aggregated_data

    initial_cap_df.to_csv(csv_out_path, index=False)

def parse_cap_max(input_path: str, csv_out_path: str, frozen_techs: list) -> None:
    """Create a file with maximum installed technology capacities using initial capacities."""
    input_df = pd.read_csv(input_path)
    frozen_cap_df = pd.DataFrame(columns=CALLIOPE_COLS)

    for tech in frozen_techs:
        tech_df = input_df[(input_df["techs"] == tech) & (input_df["parameters"].isin(FREEZE_CONVERT))].copy()
        if not tech_df.empty:
            tech_df["parameters"] = tech_df["parameters"].replace(FREEZE_CONVERT)
            frozen_cap_df = pd.concat([frozen_cap_df, tech_df])
    frozen_cap_df.to_csv(csv_out_path)


def get_techs_per_node(input_yaml_path: str) -> dict:
    """Get a dictionary specifying the technologies installed in a given region.

    Args:
        input_path (str): path to Lombardi's location.yaml

    Returns:
        dict: containing {node: [techs]}
    """
    yaml_df = _build_location_df(input_yaml_path)
    tech_df = yaml_df[yaml_df["node attribute"] == "techs"]

    replace_dict = {v: k for k, values in TECH_GROUPS.items() for v in values}
    tech_df["item"] = tech_df["item"].replace(replace_dict)

    return {n: tech_df[tech_df["node"].isin(n_group)]["item"].unique() for n, n_group in NODE_GROUPS.items()}


if __name__ == "__main__":
    input_path = "./datasets/locations_lombardi.yaml"
    installed_path = "pathways_stationary/pathways_data/inital_capacity_techs_kw.csv"
    parse_initial_cap(input_path, installed_path)
    frozen_path = "pathways_stationary/pathways_data/max_capacity_techs_kw.csv"
    frozen_tech = ["geothermal", "battery_phs", "hydropower", "waste"]
    parse_cap_max(installed_path, frozen_path, frozen_tech)
    print(get_techs_per_node(input_path))

