# Copyright (C) since 2013 Calliope contributors listed in AUTHORS.
# Licensed under the Apache 2.0 License (see LICENSE file).
"""
Generate LaTeX math to include in the documentation.
"""

import importlib.resources
import logging
import tempfile
import textwrap
from pathlib import Path

import calliope
import calliope_pathways
from mkdocs.structure.files import File

logger = logging.getLogger("mkdocs")

TEMPDIR = tempfile.TemporaryDirectory()

PREPEND_SNIPPET = """
# {title}
{description}

## A guide to math documentation

If a math component's initial conditions are met (the first `if` statement), it will be applied to a model.
For each [objective](#objective), [constraint](#subject-to) and [global expression](#where), a number of sub-conditions then apply (the subsequent, indented `if` statements) to decide on the specific expression to apply at a given iteration of the component dimensions.

In the expressions, terms in **bold** font are [decision variables](#decision-variables) and terms in *italic* font are [parameters](#parameters).
The [decision variables](#decision-variables) and [parameters](#parameters) are listed at the end of the page; they also refer back to the global expressions / constraints in which they are used.
Those parameters which are defined over time (`timesteps`) in the expressions can be defined by a user as a single, time invariant value, or as a timeseries that is [loaded from file or dataframe](../creating/data_sources.md).

!!! note

    For every math component in the documentation, we include the YAML snippet that was used to generate the math in a separate tab.

[:fontawesome-solid-download: Download the {math_type} formulation as a YAML file]({filepath})
"""


def on_files(files: list, config: dict, **kwargs):

    base_model = generate_national_scale_example_math_model()
    write_file(
        "pathways.yaml",
        textwrap.dedent(
            """
        Complete mathematical formulation for a Calliope pathway optimisation model (based on the national-scale example model).
        The downloadable math YAML file only includes additions to the [pre-defined base calliope YAML](https://calliope.readthedocs.io/en/v0.7.0.dev3/pre_defined_math/)
        """
        ),
        base_model,
        files,
        config,
    )

    return files


def write_file(
    filename: str,
    description: str,
    model: calliope.Model,
    files: list[File],
    config: dict,
) -> None:
    title = model.inputs.attrs["name"] + " math"

    output_file = (Path("math") / filename).with_suffix(".md")
    output_full_filepath = Path(TEMPDIR.name) / output_file
    output_full_filepath.parent.mkdir(exist_ok=True, parents=True)

    files.append(
        File(
            path=output_file.as_posix(),
            src_dir=TEMPDIR.name,
            dest_dir=config["site_dir"],
            use_directory_urls=config["use_directory_urls"],
        )
    )

    # Append the source file to make it available for direct download
    files.append(
        File(
            path=(Path("math") / filename).as_posix(),
            src_dir=Path(importlib.resources.files("calliope_pathways")).as_posix(),
            dest_dir=config["site_dir"],
            use_directory_urls=config["use_directory_urls"],
        )
    )
    nav_reference = [
        idx
        for idx in config["nav"]
        if isinstance(idx, dict) and set(idx.keys()) == {"Math Documentation"}
    ][0]

    nav_reference["Math Documentation"].append(output_file.as_posix())

    math_doc = model.math_documentation.write(format="md", mkdocs_tabbed=True)
    file_to_download = Path("..") / filename
    output_full_filepath.write_text(
        PREPEND_SNIPPET.format(
            title=title.capitalize(),
            description=description,
            math_type=title.lower(),
            filepath=file_to_download,
        )
        + math_doc
    )


def generate_national_scale_example_math_model() -> calliope.Model:
    """Generate model with documentation for the base math

    Args:
        model_config (dict): Calliope model config.

    Returns:
        calliope.Model: Base math model to use in generating math docs.
    """
    model = calliope_pathways.models.national_scale()
    model.math_documentation.build()
    return model
