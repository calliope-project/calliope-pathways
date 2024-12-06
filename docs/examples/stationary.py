# ---
# jupyter:
#   jupytext:
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.1
#   kernelspec:
#     display_name: calliope_docs_pathways
#     language: python
#     name: calliope_docs_pathways
# ---

# %% [markdown]
# # Stationary example of pathway optimisation
#
# This example solves a bounded stationary pathway optimisation problem.
# It is based on the Italy model developed in <https://github.com/FLomb/Calliope-Italy>, with lower spatial resolution.

# %%

import calliope
import calliope_pathways
import plotly.express as px

OUTPUT_PATH = "outputs/"

calliope.set_log_verbosity("INFO", include_solver_output=False)

# %% [markdown]
# ## Model input

# %%
# Initialise
model = calliope_pathways.models.italy()

# %% [markdown]
# ### Assessing the input data
#
# The model can be configured by running the script in `src/calliope_pathways/models/italy/pre_processing/parse_lombardi.py`.
# It automatically assigns random decommission rates for each technology, accounting for their lifetimes.
# The number of `vintagesteps` and `investsteps` can be altered when calling the model (e.g., `:::python calliope_pathways.models.italy(first_year=2030, investstep_resolution=10)`).

# %%
model.inputs.investsteps

# %%
model.inputs.vintagesteps

# %% [markdown]
# Stationary means that both costs and demand remain constant across the years:

# %%
model.inputs.cost_flow_cap.to_series().dropna()

# %% [markdown]
# ### Initial capacity
#
# The model is initialized with the capacity of Italy in 2015.

# %%
model.inputs.flow_cap_initial.to_series().dropna()

# %% [markdown]
# This technology capacity can then be phased out as we step through to the end of our time horizon:

# %%
# This is a fraction of the initial capacity that remains available in investment steps
model.inputs.available_initial_cap.to_series().dropna()

# %% [markdown]
# End-of-life decommissioning is tracked with a similar matrix.
#
# Note how vintages are never available in investsteps that are in their _future_.

# %%
model.inputs.available_vintages.to_series().dropna().unstack("investsteps")

# %% [markdown]
# ## Building a pathways optimisation problem
#
# We have created a math YAML file with updates to all the pre-defined math to handle the existence of `investsteps` and `vintagesteps`.
# Tracking new capacity in each investment period and linking it to technology vintages requires new variables and constraints

# %% [markdown]
# ### Variables

# %%
# Note the "investsteps" dimension added to this pre-defined variable
model.math["variables"]["flow_cap"]

# %%
# This new variable tracks the amount of each technology vintage that exists
model.math["variables"]["flow_cap_new"]

# %% [markdown]
# ### Constraints

# %%
# All existing constraints have the "investsteps" dimension added.
# This allows the dispatch decisions to be optimised individually for each investment step.
model.math["constraints"]["system_balance"]

# %%
# In each investment period, capacities are a combination of all available vintages.
model.math["constraints"]["flow_cap_bounding"]

# %%
# Similarly, note that some technologies cannot go beyond their initial installed capacity.
model.inputs.flow_cap_max.to_series().dropna()

# %% [markdown]
# ### Building

# %%
model.build()

# %% [markdown]
# ## Analyse results

# %%
model.solve()

# %%
df_capacity = (
    model.results.flow_cap.where(model.results.techs != "demand_electricity")
    .sel(carriers="electricity")
    .sum("nodes")
    .to_series()
    .where(lambda x: x != 0)
    .dropna()
    .to_frame("Flow capacity (kW)")
    .reset_index()
)

print(df_capacity.head())

fig = px.bar(
    df_capacity,
    x="investsteps",
    y="Flow capacity (kW)",
    color="techs",
    color_discrete_map=model.inputs.color.to_series().to_dict(),
)
fig.show()

# %%
df_capacity = (
    model.results.storage_cap.sum("nodes")
    .to_series()
    .where(lambda x: x != 0)
    .dropna()
    .to_frame("Storage capacity (kWh)")
    .reset_index()
)

print(df_capacity.head())

fig = px.bar(
    df_capacity,
    x="investsteps",
    y="Storage capacity (kWh)",
    color="techs",
    color_discrete_map=model.inputs.color.to_series().to_dict(),
)
fig.show()

# %%
df_capacity = (
    model.results.flow_cap_new.where(model.results.techs != "demand_electricity")
    .sel(carriers="electricity")
    .sum("nodes")
    .to_series()
    .where(lambda x: x != 0)
    .dropna()
    .to_frame("New flow capacity (kW)")
    .reset_index()
)

print(df_capacity.head())

fig = px.bar(
    df_capacity,
    x="vintagesteps",
    y="New flow capacity (kW)",
    color="techs",
    color_discrete_map=model.inputs.color.to_series().to_dict(),
)
fig.show()

# %%
df_outflow = (
    (model.results.flow_out.fillna(0) - model.results.flow_in.fillna(0))
    .sel(carriers="electricity")
    .sum(["nodes", "timesteps"], min_count=1)
    .to_series()
    .where(lambda x: x > 1)
    .dropna()
    .to_frame("Annual outflow (kWh)")
    .reset_index()
)

print(df_capacity.head())

fig = px.bar(
    df_outflow,
    x="investsteps",
    y="Annual outflow (kWh)",
    color="techs",
    color_discrete_map=model.inputs.color.to_series().to_dict(),
)
df_demand = (
    model.results.flow_in.sel(techs="demand_electricity", carriers="electricity")
    .sum(["nodes", "timesteps"])
    .to_series()
    .reset_index()
)
fig.add_scatter(
    x=df_demand.investsteps, y=df_demand.flow_in, line={"color": "black"}, name="Demand"
)
fig.show()

# %%
df_electricity = (
    (model.results.flow_out.fillna(0) - model.results.flow_in.fillna(0))
    .sel(carriers="electricity")
    .sum("nodes")
    .to_series()
    .where(lambda x: x != 0)
    .dropna()
    .to_frame("Flow in/out (kWh)")
    .reset_index()
)
df_electricity_demand = df_electricity[df_electricity.techs == "demand_electricity"]
df_electricity_other = df_electricity[df_electricity.techs != "demand_electricity"]

invest_order = sorted(df_electricity.investsteps.unique())

fig = px.bar(
    df_electricity_other,
    x="timesteps",
    y="Flow in/out (kWh)",
    facet_row="investsteps",
    color="techs",
    height=1000,
    category_orders={"investsteps": invest_order},
    color_discrete_map=model.inputs.color.to_series().to_dict(),
)

showlegend = True
# we reverse the investment year order (`[::-1]`) because the rows are numbered from bottom to top.
for row, year in enumerate(invest_order[::-1]):
    demand_ = df_electricity_demand.loc[(df_electricity_demand.investsteps == year)]
    fig.add_scatter(
        x=demand_["timesteps"],
        y=-1 * demand_["Flow in/out (kWh)"],
        row=row + 1,
        col="all",
        marker_color="black",
        name="Demand",
        legendgroup="demand",
        showlegend=showlegend,
    )
    showlegend = False
fig.update_yaxes(matches=None)
fig.show()
