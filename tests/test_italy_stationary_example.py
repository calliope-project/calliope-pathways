import calliope_pathways


def test_solve_model():
    m = calliope_pathways.models.italy_stationary()
    m.build()
    m.solve()

    assert m.results.termination_condition == "optimal"
