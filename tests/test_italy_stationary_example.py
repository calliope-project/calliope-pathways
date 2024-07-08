import calliope_pathways
import pytest


def test_build_model():
    """Quick build test of the static italy model."""
    m = calliope_pathways.models.italy_stationary()
    m.build()

    # Key constraints
    assert "link_storage_level" in m.backend.constraints
    assert "flow_cap_bounding" in m.backend.constraints
    assert "storage_cap_bounding" in m.backend.constraints

    # Key parameters
    assert "flow_cap_initial" in m.backend.parameters
    assert "storage_cap_initial" in m.backend.parameters

    # Key variables
    assert "flow_cap_new" in m.backend.variables
    assert "storage_cap_new" in m.backend.variables


def test_first_year():
    """Test setting non-default first investment year."""
    m = calliope_pathways.models.italy_stationary(first_year=2030)
    assert m.inputs.investsteps[0] == 2030
    assert m.inputs.vintagesteps[0] == 2030


def test_final_year():
    """Test setting non-default final investment year"""
    m = calliope_pathways.models.italy_stationary(final_year=2040)
    assert m.inputs.investsteps[0] == 2040
    assert m.inputs.vintagesteps[0] == 2040


def test_year_step():
    """Test setting non-default investstep resolution."""
    m = calliope_pathways.models.italy_stationary(
        first_year=2020, investstep_resolution=15
    )
    assert (m.inputs.investstep_resolution == 15).all()
    assert (m.inputs.investsteps.dt.year == [2020, 2035, 2050]).all()
    assert (m.inputs.vintagesteps.dt.year == [2020, 2035, 2050]).all()


def test_bad_resolution():
    """15 year resolution doesn't fit neatly between 2025 and 2050"""
    with pytest.raises(ValueError, match="Investment resolution must fit"):
        m = calliope_pathways.models.italy_stationary(
            first_year=2025, final_year=2050, investstep_resolution=15
        )
    assert (m.inputs.investstep_resolution == 15).all()
    assert (m.inputs.investsteps.dt.year == [2020, 2035, 2050]).all()
    assert (m.inputs.vintagesteps.dt.year == [2020, 2035, 2050]).all()
