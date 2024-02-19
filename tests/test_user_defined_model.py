import calliope
import pytest
from calliope_pathways import models


@pytest.fixture
def load_example_model():
    def _load_example_model(add_pathways_math):
        model_path = (
            calliope.examples._EXAMPLE_MODEL_DIR / "national_scale" / "model.yaml"
        )
        return models.load(model_path, add_pathways_math=add_pathways_math)

    return _load_example_model


@pytest.fixture
def schema_defaults():
    return calliope.util.schema.extract_from_schema(
        calliope.util.schema.MODEL_SCHEMA, "default"
    )


def test_add_pathways_math(load_example_model):
    model = load_example_model(True)
    assert "flow_cap_bounding" in model.math.constraints.keys()
    assert "flow_cap_new" in model.math.variables.keys()
    assert "investsteps" in model.math.constraints["flow_out_max"]["foreach"]


def test_load_no_pathways_math(load_example_model):
    model = load_example_model(False)
    assert "flow_cap_bounding" not in model.math.constraints.keys()
    assert "flow_cap_new" not in model.math.variables.keys()
    assert "investsteps" not in model.math.constraints["flow_out_max"]["foreach"]


def test_parameters_in_schema(schema_defaults):
    assert schema_defaults["flow_cap_initial"] == 0
