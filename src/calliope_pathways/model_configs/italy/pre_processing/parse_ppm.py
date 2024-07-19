"""Convert powerplantmatching data to Calliope compatible data.

Provides functions to extract, process and fill powerplantmatching data.

TODO: better storage capacity filling?
Unfortunately, storage data is quite incomplete in powerplantmatching.
Related functions have been removed, as linear or logarithmic regressions do not seem
adequate when filling these values.
"""

from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import parse_lombardi as lomb
import pint_pandas  # noqa: F401, unused but necessary for unit handling.
import powerplantmatching as ppm
import pycountry
from pint import Quantity

u = pint_pandas.PintType.ureg

# TODO: these approaches are pretty forced. A yaml+schema would be a better option.
NODE_GROUPING = {
    "NORD": ["ITC1", "ITC2", "ITC3", "ITC4", "ITH1", "ITH2", "ITH3", "ITH4", "ITH5"],
    "CNOR": ["ITI1", "ITI2", "ITI3"],
    "CSUD": ["ITI4", "ITF1", "ITF3"],
    "SUD": ["ITF2", "ITF4", "ITF5", "ITF6"],
    "SICI": ["ITG1"],
    "SARD": ["ITG2"],
}
TECH_GROUPING = {
    "ccgt": {"Fueltype": "Natural Gas", "Technology": ["CCGT", "", "Steam Turbine"]},
    "hydropower": {
        "Fueltype": "Hydro",
        "Technology": ["Run-Of-River", "Reservoir", "Unknown"],
    },
    "wind": {"Fueltype": "Wind", "Technology": ["Onshore"]},
    "pv": {"Fueltype": "Solar", "Technology": ["Pv", ""]},
    "battery_phs": {
        "Fueltype": "Hydro",
        "Technology": ["Pumped Storage"],
        "Storage": True,
    },
    "waste": {
        "Fueltype": "Other",
        "Technology": ["Steam Turbine"],
    },  # Assumption: remaining powerplants use waste
    "bioenergy": {"Fueltype": "Bioenergy", "Technology": ["Steam Turbine", ""]},
    "oil": {"Fueltype": "Oil", "Technology": ["Steam Turbine", ""]},
    "geothermal": {"Fueltype": "Geothermal", "Technology": ["Steam Turbine", ""]},
    "coal": {"Fueltype": "Hard Coal", "Technology": ["CCGT", "Steam Turbine"]},
}


def extract_ppm() -> pd.DataFrame:
    """Standardizes powerplantmatching data naming and enables pint usage.

    Args:
        year: system year to extract (future/decommissioned facilities will be removed).

    Returns:
        pd.DataFrame: cleaned dataframe.
    """
    ppm_units = {
        "Capacity": "MW",
        "Efficiency": "percent",
        "DateIn": "year",
        "DateRetrofit": "year",
        "DateOut": "year",
        "lat": "deg",
        "lon": "deg",
        "Duration": "hours",
        "Volume": "m^3",
        "DamHeight": "m",
        "StorageCapacity": "MWh",
    }
    plants = ppm.powerplants(from_url=True)
    plants = plants.rename(columns={col: col.split("_")[0] for col in plants.columns})
    for col, unit in ppm_units.items():
        plants[col] = plants[col].astype(f"pint[{unit}]")

    return plants


@u.check(None, "[time]")
def transform_ppm_filter_initial_year(
    plants: pd.DataFrame, year: Quantity
) -> pd.DataFrame:
    """Removes power plants that exist outside of the given initial year.

    Args:
        year (Quantity): system year to extract (future/decommissioned facilities will be removed).

    Returns:
        pd.DataFrame: cleaned dataframe.
    """
    # Get power plant data for the relevant year (including those with NaN)
    plants = plants.loc[(plants["DateIn"] <= year) | plants["DateIn"].isna()]
    plants = plants.loc[(plants["DateOut"] >= year) | plants["DateOut"].isna()]
    return plants


def transform_ppm_add_nuts(
    plants: pd.DataFrame, nuts_file: str, nuts_level: Optional[int] = 2
) -> pd.DataFrame:
    """Assign NUTS regions to powerplants using point data (lat, lon).

    Args:
        plants (pd.DataFrame): powerplantmatching data.
        nuts_file (str): a geolocation file (geojson) with NUTS ids.
        nuts_level (Optional[int], optional): NUTS resolution to use. Defaults to 2.

    Returns:
        pd.DataFrame: powerplantmatching data with additional geodata.
    """
    # Get necessary regional data.
    spatial_df = gpd.read_file(nuts_file)
    countries_alpha2 = []
    for country in plants["Country"].unique():
        country_data = pycountry.countries.get(name=country)
        if country_data is None:
            alpha_2 = pycountry.countries.search_fuzzy(country)[0].alpha_2
        else:
            alpha_2 = country_data.alpha_2
        countries_alpha2.append(alpha_2)

    spatial_df = spatial_df.loc[spatial_df["CNTR_CODE"].isin(countries_alpha2)]
    spatial_df = spatial_df.loc[spatial_df["LEVL_CODE"] == nuts_level]

    # Set the NUTS region of each power plant.
    geo_plants = gpd.GeoDataFrame(
        plants, geometry=gpd.points_from_xy(plants.lon, plants.lat)
    )
    geo_plants = geo_plants.set_crs("epsg:4326").to_crs(crs=3857)
    geo_plants = gpd.sjoin_nearest(geo_plants, spatial_df.to_crs(geo_plants.crs))

    return geo_plants


def transform_ppm_group_tech_nodes(
    plants: pd.DataFrame, tech_grouping: dict, node_grouping: Optional[dict] = None
) -> pd.DataFrame:
    """Assign calliope data based on configuration.

    TODO: inputs should be yaml files.
    Assumes that NUTS regions have been added to the dataframe.

    Args:
        plants (pd.DataFrame): powerplantmatching data, preprocessed for NUTS regions.
        tech_grouping (dict): Technological grouping to use.
        node_grouping (Optional[dict], optional): Aggregation of regions (None -> no aggregation). Defaults to None.

    Raises:
        ValueError: If the given tech_grouping is not exhaustive.
        ValueError: If the given node_grouping is not exhaustive
    """
    # Assign a calliope technology to each power plant.
    plants["techs"] = pd.Series(np.nan, dtype="string")
    list_ppm_techs_txt = plants.Technology.fillna("")  # Make comparisons easier.
    tech_cnf = pd.DataFrame.from_dict(tech_grouping)
    for tech in tech_cnf.columns:
        fuel = tech_cnf.loc["Fueltype", tech]
        for tech_ppm in tech_cnf.loc["Technology", tech]:
            plants.loc[
                (plants.Fueltype == fuel) & (list_ppm_techs_txt == tech_ppm), "techs"
            ] = tech

    # Assign a calliope node to each power plant.
    if node_grouping is not None:
        plants = plants.assign(
            nodes=lomb.transform_series(plants["NUTS_ID"], node_grouping)
        )
    else:
        plants = plants.assign(nodes=plants["NUTS_ID"])

    if any(plants["techs"].isna()):
        raise ValueError("Not all technologies could be translated to Calliope.")
    if any(plants["nodes"].isna()):
        raise ValueError("Not all NUTS regions could be translated to Calliope.")

    return plants


def transform_ppm_capacity_to_calliope(
    plants: pd.DataFrame, parameter: str, cap_unit: Optional[str]
) -> pd.DataFrame:
    """Assigns a parameter to grouped capacity data.

    Capacity will be summed per node and per technology group.

    Args:
        plants (pd.DataFrame): powerplantmatching data, preprocessed for grouping.
        parameter (str, optional): parameter to set.

    Returns:
        pd.DataFrame: capacity data in calliope format.
    """
    grouped_plants = plants.groupby(["nodes", "techs"]).sum("Capacity")
    grouped_plants = grouped_plants.rename(columns={"Capacity": "values"})
    grouped_plants["parameters"] = parameter
    columns = lomb.BASIC_V07_COLS
    calliope_plants = grouped_plants.reset_index()[columns]

    if cap_unit:
        calliope_plants.values = calliope_plants["values"].pint.to("kW")

    return calliope_plants


def main():
    countries = ["Italy"]
    year = 2015 * u.year
    nuts_file = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326.geojson"
    save_path = "src/calliope_pathways/models/italy/data_sources/initial_capacity_techs_ppm_kw.csv"

    plants = extract_ppm()

    plants = transform_ppm_filter_initial_year(plants, year)
    plants = transform_ppm_add_nuts(plants, nuts_file, nuts_level=2)

    plants = plants.loc[plants.Country.isin(countries)]
    plants = transform_ppm_group_tech_nodes(plants, TECH_GROUPING, NODE_GROUPING)

    calliope_ini_cap = transform_ppm_capacity_to_calliope(
        plants, "flow_cap_initial", cap_unit="kW"
    )
    calliope_ini_cap.pint.dequantify().to_csv(save_path, index=False)


if __name__ == "__main__":
    main()
