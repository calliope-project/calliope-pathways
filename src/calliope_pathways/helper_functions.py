from typing import Literal

import numpy as np
import scipy
import xarray as xr
from calliope.backend.helper_functions import ParsingHelperFunction


class GetVintageAvailability(ParsingHelperFunction):
    #:
    NAME = "get_vintage_availability"
    #:
    ALLOWED_IN = ["expression"]

    def _weibull_func(self, year_diff: xr.DataArray) -> xr.DataArray:
        shape = self._input_data.get("shape", 1)
        gamma = scipy.special.gamma(1 + 1 / shape)
        availability = np.exp(
            -((year_diff / self._input_data.lifetime.fillna(np.inf)) ** shape)
            * (gamma**shape)
        )
        return availability.fillna(0)

    def _linear_func(self, year_diff: xr.DataArray) -> xr.DataArray:
        availability = 1 - (year_diff / self._input_data.lifetime)
        return availability.clip(min=0)

    def _step_func(self, year_diff: xr.DataArray) -> xr.DataArray:
        life_diff = self._input_data.lifetime - year_diff
        availability = (life_diff).clip(min=0) / life_diff
        return availability

    def as_math_string(self, method: Literal["weibull", "linear", "step"]) -> str:
        alpha = r"\textit{age}_\text{tech}"
        beta = r"\textit{shape}"
        eta = r"\textit{lifetime}_\text{tech}"
        match method:
            case "weibull":
                math_str = rf"\exp{{-(frac{{{alpha}}}{{{eta}}})^{{{beta}}}\times\Gamma{{1+frac{{1}}{{{beta}}})^{{{beta}}}}}}}"
            case "linear":
                math_str = rf"""
                \begin{{cases}}
                1\mathord{{-}}frac{{{alpha}}}{{{eta}}}, & \text{{if }} 1\mathord{{-}}frac{{{alpha}}}{{{eta}}}\gt{{}}0\\
                0, & \text{{otherwise}}\\
                \end{{cases}}
                """
            case "step":
                math_str = rf"""
                \begin{{cases}}
                1, & \text{{if }} {eta}\mathord{{-}}{alpha}\gt{{}}0\\
                0, & \text{{otherwise}}\\
                \end{{cases}}
                """
            case _:
                raise ValueError(
                    f"Cannot get vintage availability with `method`: {method}"
                )
        return math_str

    def as_array(self, method: Literal["weibull", "linear", "step"]) -> xr.DataArray:
        """For each investment step in pathway optimisation, get the remaining availability of each historical capacity addition as a fraction.

        Args:
            method (Literal[weibull, linear, step]):
                The method used to describe the ageing curve of the historical capacity:
                - weibull: Apply a weibull function to produce technology survival curves. See <https://doi.org/10.1186/s12544-020-00464-0> for more detail.
                - linear: Apply a linear ageing, such that 50% of the technology capacity exists half way through the technology lifetime.
                - step: Apply a function such that 100% of the technology capacity exists until the distance between the deployment and investment years is greater than the technology age.

        Returns:
            xr.DataArray: Array of vintage availabilities as fractions. Any index items referring to vintage year > investment year are nullified.
        """
        year_diff = (
            self._input_data.investsteps.dt.year - self._input_data.vintagesteps.dt.year
        )
        year_diff_no_negative = year_diff.where(year_diff >= 0)
        match method:
            case "weibull":
                availability = self._weibull_func(year_diff_no_negative)
            case "linear":
                availability = self._linear_func(year_diff_no_negative)
            case "step":
                availability = self._step_func(year_diff_no_negative)
            case _:
                raise ValueError(
                    f"Cannot get vintage availability with `method`: {method}"
                )
        return availability.where(year_diff_no_negative.notnull()).fillna(0)


class Resolution(ParsingHelperFunction):
    #:
    NAME = "resolution"
    #:
    ALLOWED_IN = ["expression"]

    def as_math_string(self, array: str) -> str:
        return f"resolution({array})"

    def as_array(self, array: xr.DataArray, base_resolution: int = 1) -> xr.DataArray:
        assert len(array.dims) == 1
        diff_array = (
            array.diff(array.name, label="lower")
            .reindex({array.name: array})
            .ffill(array.name)
        )
        if len(array) == 1:
            return diff_array.fillna(base_resolution)
        else:
            return diff_array


class Year(ParsingHelperFunction):
    #:
    NAME = "year"
    #:
    ALLOWED_IN = ["where", "expression"]

    def as_math_string(self, array: str) -> str:
        return f"year({array})"

    def as_array(self, array: xr.DataArray) -> xr.DataArray:
        return array.dt.year
