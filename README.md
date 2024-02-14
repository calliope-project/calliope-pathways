# calliope-pathways

Pathway optimisation implementation built on top of Calliope v0.7

## Install

You can install calliope pathways in one of two ways:

As a user:

```shell
mamba env create -f environment.yml
```

As a developer:

```shell
mamba create -n calliope-pathways -c conda-forge/label/calliope_dev -c conda-forge -f requirements/base.txt -f requirements/dev.txt
mamba activate calliope-pathways
pip install --no-deps -e .
```
