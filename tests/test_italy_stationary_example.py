import calliope_pathways


def test_solve_model():
    """Quick build test of the static italy model using extreme resampling."""
    m = calliope_pathways.models.italy_stationary()
    m.build()

