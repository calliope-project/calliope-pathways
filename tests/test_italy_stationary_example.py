import calliope_pathways


def test_solve_model():
    """Quick build test of the static italy model using extreme resampling."""
    overrides = {"config.solve.solver": "cbc",
                 "config.init.time_resample": "8760h"}
    m = calliope_pathways.models.italy_stationary(override_dict=overrides)
    m.build()

