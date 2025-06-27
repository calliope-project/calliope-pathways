"""Convert powerplantmatching data to Calliope compatible data.

Provides functions to extract, process and fill powerplantmatching data.

TODO: better storage capacity filling?
Unfortunately, storage data is quite incomplete in powerplantmatching.
Related functions have been removed, as linear or logarithmic regressions do not seem
adequate when filling these values.
"""

from typing import Optional, Literal
import geopandas as gpd
import numpy as np
import pandas as pd
import pint_pandas  # noqa: F401, unused but necessary for unit handling.
import powerplantmatching as ppm
import pycountry
from pint import Quantity

from calliope_pathways import util
u = pint_pandas.PintType.ureg
NUTS_FILE = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2021_4326.geojson"
TECH_GROUPING = {
    # Assumption: "Other" powerplants use gas
    "ccgt": {"Fueltype": ["Natural Gas", "Other"], "Technology": ["CCGT", "Steam Turbine", "Not Found", "Unknown", "Combustion Engine"]},
    "hydropower": {
        "Fueltype": ["Hydro"],
        "Technology": ["Run-Of-River", "Reservoir", "Unknown"],
    },
    "wind_onshore": {"Fueltype": ["Wind"], "Technology": ["Onshore"]},
    "wind_offshore": {"Fueltype": ["Wind"], "Technology": ["Offshore", "Offshore Mount Unknown", "Offshore Hard Mount"]},
    "pv": {"Fueltype": ["Solar"], "Technology": ["Pv", "Assumed Pv", "Unknown"]},
    "battery_phs": {
        "Fueltype": ["Hydro"],
        "Technology": ["Pumped Storage"],
        "Storage": True,
    },
    "waste": {
        "Fueltype": ["Waste"],
        "Technology": ["Steam Turbine", "Unknown", "CCGT"],
    },
    "bioenergy": {"Fueltype": ["Bioenergy"], "Technology": ["Steam Turbine", "Unknown", "Combustion Engine"]},
    "oil": {"Fueltype": ["Oil"], "Technology": ["Steam Turbine", "Unknown"]},
    "geothermal": {"Fueltype": ["Geothermal"], "Technology": ["Steam Turbine", "Unknown"]},
    "coal": {"Fueltype": ["Hard Coal", "Lignite"], "Technology": ["CCGT", "Steam Turbine", "Unknown"]},
    "nuclear": {"Fueltype": ["Nuclear"], "Technology": ["Steam Turbine"]},
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
    countries_alpha2 = util.convert_country(plants["Country"].unique(), "name", "alpha_2")
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
    plants: pd.DataFrame, tech_grouping: dict, node_grouping: dict | Literal["Country"] | None
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
    list_ppm_techs_txt = plants.Technology.fillna("Unknown")  # Make comparisons easier.
    tech_cnf = pd.DataFrame.from_dict(tech_grouping)
    for tech in tech_cnf.columns:
        plants.loc[
            (plants.Fueltype.isin(tech_cnf.loc["Fueltype", tech])) & (list_ppm_techs_txt.isin(tech_cnf.loc["Technology", tech])), "techs"
        ] = tech

    # Assign a calliope node to each power plant.
    if isinstance(node_grouping, dict):
        plants = plants.assign(
            nodes=util.transform_series(plants["NUTS_ID"], node_grouping)
        )

    # Assign a calliope node to each power plant.
    elif node_grouping == "Country":
        plants = plants.assign(
            nodes=util.convert_country(plants["Country"], "name", "alpha_3")
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
    columns = util.BASIC_V07_COLS
    calliope_plants = grouped_plants.reset_index()[columns]

    if cap_unit:
        calliope_plants.values = calliope_plants["values"].pint.to("kW")

    return calliope_plants

def parse(countries: list[str], year: int, agg: Literal["Country"] | dict | None = "Country") -> pd.DataFrame:
    year *= u.year

    plants = extract_ppm()

    plants = transform_ppm_filter_initial_year(plants, year)
    plants = transform_ppm_add_nuts(plants, NUTS_FILE, nuts_level=2)
    plants = plants.loc[plants.Country.isin(util.convert_country(countries, "alpha_3", "name"))]
    plants = transform_ppm_group_tech_nodes(plants, TECH_GROUPING, agg)

    calliope_ini_cap = transform_ppm_capacity_to_calliope(
        plants, "flow_cap_initial", cap_unit="kW"
    )
    return calliope_ini_cap.pint.dequantify()
