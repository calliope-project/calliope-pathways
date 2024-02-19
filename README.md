# calliope-pathways - pathway optimisation in Calliope

[![Documentation Status](https://readthedocs.org/projects/calliope-pathways/badge/?version=latest)](https://calliope-pathways.readthedocs.io/en/latest/?badge=latest)

Pathway optimisation implementation built on top of Calliope v0.7.

The purpose of this repository is to store both the mathematical formulation and the toy models of pathway optimisation experiments.
The main branch contains the most up-to-date version of the models and the math; branches include active experiments into methods to improve the math representation of pathway optimisation.

## Install

You can install calliope pathways in one of two ways:

As a user:

```shell
mamba env create -f environment.yml
mamba activate calliope-pathways
```

As a developer on WINDOWS:

```shell
mamba create -n calliope-pathways-dev -c conda-forge/label/calliope_dev -c conda-forge --file requirements/base.txt --file requirements/dev.txt
mamba activate calliope-pathways-dev
pip install --no-deps -e .
```

As a developer on UNIX:

```shell
mamba create -n calliope-pathways-dev -c conda-forge/label/calliope_dev -c conda-forge --file requirements/base.txt --file requirements/dev.txt
mamba activate calliope-pathways-dev
pip install --no-deps -e .
```

### Installing a solver

We recommend you use Gurobi if you have access to a license, otherwise use CBC.

To install CBC into your mamba environment on Windows:

```shell
mamba install curl
curl -L https://github.com/coin-or/Cbc/releases/download/releases%2F2.10.10/Cbc-releases.2.10.10-w64-msvc17-md.zip -o cbc.zip
unzip cbc.zip "bin/*" -d %CONDA_PREFIX%
```

To install CBC into your mamba environment on MacOS / Linux:

```shell
mamba install coin-or-cbc
```

## Run a pre-defined model

You can find examples of loading and running a pre-defined pathways optimisation model under "Examples and tutorial" in our documentation.

## Build your own model

To use pathway optimisation with your own model, use the `calliope.models.load(...)` function.
This will add pathways math to your model math and parameter metadata to the calliope schema.
Your pathways model will need to define:

* The `investsteps` and `vintagesteps` dimensions.
* Initial capacities of your technologies, setting the starting conditions of your model:
    * `flow_cap_initial`
    * `area_use_initial`
    * `storage_cap_initial`
    * `source_cap_initial`
* The length of time your technologies are available after deployment (for new capacity) or from the first investment step (for initial capacity).
This is given as fractions per investment step.
Values between `0` and `1` allow you to represent technologies being phased out _between_ investment steps.
    * `available_initial_cap`: this should be an array of fractions indexed over the `investsteps` dimension.
    `1` means all initial capacity is still available in that investment step, `0` means that none of it is available.
    * `available_vintages`: this should be an array of fractions indexed over the `investsteps` and `vintagesteps` dimensions.
    `1` means all of a technology vintage's capacity is still available in that investment step, `0` means that none of it is available.
    For instance, a "2030" technology vintage with a 20-year lifetime will be fully available in the "2030" and "2040" investment steps, but no longer available in "2050".
    A "2030" technology vintage with a 15-year lifetime will be fully available in the "2030", but only 50% available in a "2040" investment step, then no longer available in "2050".
* `investstep_resolution`: the weights of your investment steps, indexed over `investsteps`.
This will likely be the number of years between your investment steps (e.g. a value of `10` for the steps [2030, 2040, 2050]).

We expect to automate the generation of some of this data in future (e.g., capacity availability using technology lifetime, investment step resolution based on the `diff` of `investsteps`).
In the meantime, we ask that you define the data explicitly in your model YAML / tabular data files.

## Acknowledgements

This repository structure and content is based heavily on the [`Calliope` repository](https://github.com/calliope-project/calliope).

See the [callio.pe project website](https://www.callio.pe/partners-and-team/) for current and past team members and acknowledgements for Calliope.

## License

Copyright since 2024 Calliope pathways contributors listed in AUTHORS. Licensed under MIT.
