# calliope-pathways

[![Documentation Status](https://readthedocs.org/projects/calliope-pathways/badge/?version=latest)](https://calliope-pathways.readthedocs.io/en/latest/?badge=latest)

Pathway optimisation implementation built on top of Calliope v0.7

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
