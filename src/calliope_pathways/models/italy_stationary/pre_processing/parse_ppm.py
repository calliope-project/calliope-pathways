from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import pint_pandas  # noqa: F401, unused but necessary for unit handling.
import powerplantmatching as ppm
import pycountry

# TODO: these approaches are pretty forced. A yaml+schema would be a better option.
NODE_GROUPING = {
    "NORD": [
        "ITC1",
        "ITC2",
        "ITC3",
        "ITC4",
        "ITH1",
        "ITH2",
        "ITH3",
        "ITH4",
        "ITH5",
    ],
    "CNOR": ["ITI1", "ITI2", "ITI3"],
    "CSUD": ["ITI4", "ITF1", "ITF3"],
    "SUD": ["ITF2", "ITF4", "ITF5", "ITF6"],
    "SICI": ["ITG1"],
    "SARD": ["ITG2"],
}
TECH_GROUPING = {
    "ccgt": {
        "Fueltype": "Natural Gas",
        "Technology": ["CCGT", "", "Steam Turbine"],
        "parameter": "flow_cap_initial",
    },
    "hydropower": {
        "Fueltype": "Hydro",
        "Technology": ["Run-Of-River", "Reservoir", "Unknown"],
        "parameter": "flow_cap_initial",
    },
    "wind": {
        "Fueltype": "Wind",
        "Technology": ["Onshore"],
        "parameter": "flow_cap_initial",
    },
    "pv": {
        "Fueltype": "Solar",
        "Technology": ["Pv", ""],
        "parameter": "flow_cap_initial",
    },
    "battery_phs": {
        "Fueltype": "Hydro",
        "Technology": ["Pumped Storage"],
        "parameter": "storage_cap_initial",
    },
    "waste": {
        "Fueltype": "Other",
        "Technology": ["Steam Turbine"],
        "parameter": "flow_cap_initial",
    },  # Assumption: remaining powerplants use waste
    "bioenergy": {
        "Fueltype": "Bioenergy",
        "Technology": ["Steam Turbine", ""],
        "parameter": "flow_cap_initial",
    },
    "oil": {
        "Fueltype": "Oil",
        "Technology": ["Steam Turbine", ""],
        "parameter": "flow_cap_initial",
    },
    "geothermal": {
        "Fueltype": "Geothermal",
        "Technology": ["Steam Turbine", ""],
        "parameter": "flow_cap_initial",
    },
    "coal": {
        "Fueltype": "Hard Coal",
        "Technology": ["CCGT", "Steam Turbine"],
        "parameter": "flow_cap_initial",
    },
}
BASIC_V07_COLS = ["nodes", "techs", "parameters", "values"]


def ppm_extract_plants(
    country_names: list[str],
    year: int,
    cap_unit: Optional[str] = None,
    storage_unit: Optional[str] = None,
) -> pd.DataFrame:
    """Start powerplant data for a set of countries.

    Args:
        country_names (list[str]): full country names to extract.
        year (int): system year to extract (future/decomissioned facilities will be removed).
        cap_unit (Optional[str]): unit for capacity (uses pint).
        storage_unit (Optional[str]): unit for storage (uses pint).

    Returns:
        pd.DataFrame: cleaned dataframe.
    """
    # Get power plant data for the relevant year (including those with NaN)
    plants = ppm.powerplants(from_url=True)
    plants = plants.loc[(plants["Country"].isin(country_names))]
    plants = plants.loc[(plants["DateIn"] <= year) | plants["DateIn"].isna()]
    plants = plants.loc[(plants["DateOut"] > year) | plants["DateOut"].isna()]

    # Standardize units and fix potentially confusing naming
    plants.Capacity = plants.Capacity.astype("pint[MW]")
    plants = plants.rename(columns={"StorageCapacity_MWh": "StorageCapacity"})
    plants["StorageCapacity"] = plants.StorageCapacity.astype("pint[MWh]")
    if cap_unit is not None:
        plants.Capacity = plants.Capacity.pint.to(cap_unit)
    if storage_unit is not None:
        plants.Capacity = plants.StorageCapacity.pint.to(storage_unit)

    return plants


def ppm_add_nuts_region(
    plants: pd.DataFrame,
    nuts_file: str,
    country_names: list[str],
    nuts_level: Optional[int] = 2,
):
    # Get necessary regional data.
    spatial_df = gpd.read_file(nuts_file)
    country_alpha2 = [pycountry.countries.get(name=i).alpha_2 for i in country_names]
    spatial_df = spatial_df.loc[spatial_df["CNTR_CODE"].isin(country_alpha2)]
    spatial_df = spatial_df.loc[spatial_df["LEVL_CODE"] == nuts_level]

    # Set the NUTS region of each powerplant.
    plants = gpd.GeoDataFrame(
        plants, geometry=gpd.points_from_xy(plants.lon, plants.lat)
    )
    plants = plants.set_crs("epsg:4326").to_crs(crs=3857)
    plants = gpd.sjoin_nearest(plants, spatial_df.to_crs(plants.crs))

    return plants


def ppm_get_calliope_ini_cap(
    plants: pd.DataFrame, tech_grouping: dict, node_grouping: Optional[dict] = None
) -> pd.DataFrame:
    """Extract initial capacity from a powerplantmaching dataframe.

    Assumes that NUTS regions have been added to the dataframe.

    Args:
        plants (pd.DataFrame): powerplantmatching data, preprocessed for NUTS regions.
        tech_grouping (dict): Technological grouping to use.
        node_grouping (Optional[dict], optional): Aggregation of regions (None -> no aggregation). Defaults to None.

    Raises:
        ValueError: If the given tech_grouping is not exhaustive.
        ValueError: If the given node_grouping is not exhaustive

    Returns:
        pd.DataFrame: initial capacity data in calliope format.
    """
    # Assign a calliope technology for each power plant.
    plants.Technology = plants.Technology.fillna("")  # Makes comparisons easier.
    plants["techs"] = pd.Series(np.nan, dtype="string")
    for tech, tech_cnf  in tech_grouping.items():
        fuel = tech_cnf["Fueltype"]
        parameter = tech_cnf["parameter"]
        for tech_ppm in tech_grouping[tech]["Technology"]:
            tech_check = (plants.Fueltype == fuel) & (plants.Technology == tech_ppm)
            plants.loc[tech_check, "techs"] = tech
            plants.loc[tech_check, "parameters"] = parameter

    # Assign a calliope node for each region.
    if node_grouping is not None:
        plants["nodes"] = pd.Series(np.nan, dtype="string")
        for node, group in node_grouping.items():
            plants.loc[(plants.NUTS_ID.isin(group)), "nodes"] = node
    else:
        plants["nodes"] = plants["NUTS_ID"]

    if any([pd.isna(i) for i in plants["techs"]]):
        raise ValueError("Not all technologies could be translated to Calliope.")
    if any([pd.isna(i) for i in plants["nodes"]]):
        raise ValueError("Not all NUTS regions could be translated to Calliope.")

    # Transform to a calliope compatible dataframe.
    grouped_plants = plants.groupby(["nodes", "techs", "parameters"]).sum("Capacity")
    grouped_plants = grouped_plants.rename(columns={"Capacity": "values"})
    columns = ["nodes", "techs", "parameters", "values"]
    calliope_plants = grouped_plants.reset_index()[columns]

    return calliope_plants


def main():
    countries = ["Italy"]
    year = 2015
    nuts_file = "src/calliope_pathways/models/italy_stationary/data_sources/NUTS_RG_20M_2021_4326.geojson"
    save_path = "src/calliope_pathways/models/italy_stationary/data_sources/initial_capacity_techs_ppm_kw.csv"

    plants = ppm_extract_plants(countries, year, cap_unit="kW")
    plants = ppm_add_nuts_region(plants, nuts_file, countries, nuts_level=2)
    calliope_ini_cap = ppm_get_calliope_ini_cap(plants, TECH_GROUPING, NODE_GROUPING)
    calliope_ini_cap["values"] = calliope_ini_cap["values"].pint.magnitude
    calliope_ini_cap.to_csv(save_path, index=False)


if __name__ == "__main__":
    main()
