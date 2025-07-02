"""List of lazy parsing scripts to convert files from Lombardi's study."""

import importlib
import importlib.resources
from pathlib import Path

import pandas as pd
import requests
from calliope import io
from calliope_pathways import availability_curves, util

SRC_DIR = Path(importlib.resources.files("calliope_pathways"))
# TODO: this could be a yaml file + schema... although it may be too specific
# -> Model setup -> User configurable
# Technologies with no growth
FROZEN_TECHS = ["geothermal", "battery_phs", "hydropower", "waste"]
TRANSMISSION_TECHS = [
    "ac_NORD_to_CNOR",
    "ac_CNOR_to_CSUD",
    "ac_CNOR_to_SARD",
    "ac_CSUD_to_SARD",
    "ac_CSUD_SUD",
    "ac_SUD_to_SICI",
    "ac_NORD_to_EUC",
    "ac_SUD_to_GRE",
]
# <- Model setup <-

# -> Parsing setup -> DO NOT MODIFY!
INPUT_FILES = {
    "Calliope-Italy": {
        "locations": "https://raw.githubusercontent.com/FLomb/Calliope-Italy/power_to_heat/italy_20_regions_v.0.1_heat/calliope_model/model_config/locations.yaml"
    }
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
    "import_electricity": ["import_electricity"],
    "export_electricity": ["export_electricity"],
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
PARAM_INI_CAP_GROUPING = {
    "flow_cap_initial": ["energy_cap_equals"],
    "storage_cap_initial": ["storage_cap_equals"],
}
PARAM_INI_TO_MAX = {
    "flow_cap_initial": "flow_cap_max",
    "storage_cap_initial": "storage_cap_max",
}
# <- Parsing setup <-


def _location_yaml_to_df(
    yaml_data: dict, calliope_version: str = "0.6.8"
) -> pd.DataFrame:
    """Converts a location yaml into a searchable dataframe."""
    # Read yaml file
    if calliope_version == "0.6.8":
        yaml_df = pd.json_normalize(yaml_data["locations"])
        yaml_df = yaml_df.T.reset_index()
        yaml_df.columns = ["commands", "values"]

        # Arrange commands into something sensible
        command_split = [
            "lombardi_loc",
            "lombardi_loc_attr",
            "lombardi_item",
            "lombardi_item_attr",
            "lombardi_param",
        ]
        yaml_df[command_split] = yaml_df["commands"].str.split(".", expand=True)
        yaml_df = yaml_df.drop(columns="commands")
    else:
        raise ValueError(f"Version {calliope_version} not supported.")
    return yaml_df


def parse_initial_cap(loc_yml_path: str, calliope_version="0.6.8") -> pd.DataFrame:
    """Extract initial installed capacity (2015 values)."""
    yml_loc = io.read_rich_yaml(requests.get(loc_yml_path).text)
    df_loc = _location_yaml_to_df(yml_loc, calliope_version)

    # Find exclusively numeric tech parameters in each location
    df_loc_tech = df_loc[
        (df_loc["lombardi_loc_attr"] == "techs")
        & (df_loc["lombardi_item_attr"] == "constraints")
        & (df_loc["lombardi_param"] != "resource")
    ]
    if any(pd.isna(df_loc_tech["values"])):
        raise ValueError("Empty numeric parameter values in parsed Lombardi data.")

    df_loc_tech = df_loc_tech.assign(
        nodes=util.transform_series(df_loc_tech["lombardi_loc"], NODE_GROUPING)
    )
    df_loc_tech = df_loc_tech.assign(
        techs=util.transform_series(df_loc_tech["lombardi_item"], TECH_GROUPING)
    )
    df_loc_tech = df_loc_tech.assign(
        parameters=util.transform_series(
            df_loc_tech["lombardi_param"], PARAM_INI_CAP_GROUPING
        )
    )

    # build initial capacity datafile
    df_ini_cap = df_loc_tech.groupby(["nodes", "techs", "parameters"]).sum()["values"]
    df_ini_cap = df_ini_cap.reset_index()[util.BASIC_V07_COLS]

    return df_ini_cap


def main(
    first_year: int = 2025,
    final_year: int = 2050,
    investstep_resolution: int = 5,
    model_dir: str | Path = SRC_DIR / "model_configs" / "italy",
    data_dir: str | Path = SRC_DIR / "model_configs" / "italy",
) -> list[dict]:
    """Parse Italian model pathways tables using Lombardi paper initial capacities.

    Args:
        first_year (int, optional): First investment year of the pathway optimisation. Defaults to 2025.
        final_year (int, optional): Final investment year of the pathway optimisation. Defaults to 2050.
        investstep_resolution (int, optional): Steps between pathway investment periods. Defaults to 5.
        model_dir (str | Path, optional): Italian model directory. Defaults to SRC_DIR/"model_configs"/"italy".
        data_dir (str | Path, optional): Directory in which to store data generated by this method. Defaults to SRC_DIR/"model_configs"/"italy".

    Returns:
        list[dict]: _description_
    """
    ini_cap = parse_initial_cap(INPUT_FILES["Calliope-Italy"]["locations"])
    data_table_dict = availability_curves.parse(
        Path(data_dir),
        ini_cap,
        util.get_lifetimes(Path(model_dir) / "model_config" / "techs.yaml"),
        FROZEN_TECHS,
        TRANSMISSION_TECHS,
        first_year,
        final_year,
        investstep_resolution,
        absolute_paths=True,
    )

    return data_table_dict


if __name__ == "__main__":
    main()
