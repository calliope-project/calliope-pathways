from typing import Literal, Optional

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

    def as_array(self, method: Literal["weibull", "linear", "step"]) -> xr.DataArray:
        """For each investment step in pathway optimisation, get the historical capacity additions that now must be decommissioned.

        Args:
            array (xr.DataArray): A capacity decision variable (`flow_cap`, `storage_cap`, etc.)

        Returns:
            xr.DataArray:
        """
        year_diff = (
            self._input_data.investsteps.dt.year - self._input_data.vintagesteps.dt.year
        )
        year_diff_no_negative = year_diff.where(year_diff >= 0)
        if method == "weibull":
            availability = self._weibull_func(year_diff_no_negative)
        elif method == "linear":
            availability = self._linear_func(year_diff_no_negative)
        elif method == "step":
            availability = self._step_func(year_diff_no_negative)
        else:
            raise ValueError(f"Cannot get vintage availability with `method`: {method}")
        return availability.where(year_diff_no_negative.notnull())


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


class Exponential(ParsingHelperFunction):
    #:
    NAME = "exponential"
    #:
    ALLOWED_IN = ["expression"]

    def as_math_string(self, array: str) -> str:
        return rf"\exp^{{{array}}}"

    def as_array(self, array: xr.DataArray) -> xr.DataArray:
        return np.exp(array)


class Gamma(ParsingHelperFunction):
    #:
    NAME = "gamma"
    #:
    ALLOWED_IN = ["expression"]

    def as_math_string(self, array: str) -> str:
        return rf"\Gamma({array})"

    def as_array(self, array: xr.DataArray) -> xr.DataArray:
        return scipy.special.gamma(array)


class Clip(ParsingHelperFunction):
    #:
    NAME = "clip"
    #:
    ALLOWED_IN = ["expression"]

    def as_math_string(
        self, array: str, lower: Optional[str] = None, upper: Optional[str] = None
    ) -> str:
        base = rf"\text{{clip}}({array}"
        if lower is not None:
            base += rf", \text{{lower}}={lower}"
        if upper is not None:
            base += rf", \text{{upper}}={upper}"
        return base + ")"

    def as_array(
        self,
        array: xr.DataArray,
        lower: Optional[str] = None,
        upper: Optional[str] = None,
    ) -> xr.DataArray:
        return array.clip(min=lower, max=upper)
