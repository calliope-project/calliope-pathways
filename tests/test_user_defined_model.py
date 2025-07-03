from pathlib import Path

import calliope
import pytest

from calliope_pathways import models
from calliope_pathways.util import src_dir_ref


@pytest.fixture
def load_example_model():
    def _load_example_model(model_path: Path, add_pathways_math: bool):
        loaded = models.load(model_path, add_pathways_math=add_pathways_math)
        loaded.build()
        return loaded

    return _load_example_model


@pytest.fixture
def schema_defaults():
    return calliope.util.schema.extract_from_schema(
        calliope.util.schema.MODEL_SCHEMA, "default"
    )


def test_add_pathways_math(load_example_model):
    model = load_example_model(
        src_dir_ref("model_configs") / "national_scale" / "model.yaml", True
    )
    assert "flow_cap_bounding" in model.applied_math.data["constraints"].keys()
    assert "flow_cap_new" in model.applied_math.data["variables"].keys()
    assert (
        "investsteps"
        in model.applied_math.data["constraints"]["flow_out_max"]["foreach"]
    )


def test_load_no_pathways_math(load_example_model):
    model = load_example_model(
        calliope.examples._EXAMPLE_MODEL_DIR / "national_scale" / "model.yaml", False
    )
    assert "flow_cap_bounding" not in model.applied_math.data["constraints"].keys()
    assert "flow_cap_new" not in model.applied_math.data["variables"].keys()
    assert (
        "investsteps"
        not in model.applied_math.data["constraints"]["flow_out_max"]["foreach"]
    )


def test_parameters_in_schema(schema_defaults):
    assert schema_defaults["flow_cap_initial"] == 0
