import calliope_pathways


def test_solve_model():
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
