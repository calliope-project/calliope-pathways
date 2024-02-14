import calliope_pathways


def test_solve_model():
    m = calliope_pathways.models.national_scale()
    m.build()
    m.solve()

    assert m.results.termination_condition == "optimal"
