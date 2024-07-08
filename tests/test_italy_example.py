import calliope_pathways
import pytest


class TestStationary:
    def test_build_model(self):
        """Quick build test of the static italy model."""
        m = calliope_pathways.models.italy()
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

    def test_first_year(self):
        """Test setting non-default first investment year."""
        m = calliope_pathways.models.italy(first_year=2030)
        assert m.inputs.investsteps.dt.year[0].item() == 2030
        assert m.inputs.vintagesteps.dt.year[0].item() == 2030

    def test_final_year(self):
        """Test setting non-default final investment year"""
        m = calliope_pathways.models.italy(final_year=2040)
        assert m.inputs.investsteps.dt.year[-1].item() == 2040
        assert m.inputs.vintagesteps.dt.year[-1].item() == 2040

    def test_year_step(self):
        """Test setting non-default investstep resolution."""
        m = calliope_pathways.models.italy(first_year=2020, investstep_resolution=15)
        assert (m.inputs.investstep_resolution == 15).all()
        assert (m.inputs.investsteps.dt.year == [2020, 2035, 2050]).all()
        assert (m.inputs.vintagesteps.dt.year == [2020, 2035, 2050]).all()

    def test_bad_resolution(self):
        """15 year resolution doesn't fit neatly between 2025 and 2050"""
        with pytest.raises(ValueError, match="Investment resolution must fit"):
            calliope_pathways.models.italy(
                first_year=2025, final_year=2050, investstep_resolution=15
            )


class TestDynamic:
    def test_build_model(self):
        """Quick build test of the static italy model."""
        m = calliope_pathways.models.italy(scenario="dynamic")
        m.build()

        # Key constraints
        assert "limit_flow_cap_new_max_rate" in m.backend.constraints
