"""
Construct a single-node PyPSA network for Luxembourg electricity system.
All input data loading and manipulations are handled with Polars.
"""

from math import sqrt
from pathlib import Path
from typing import Optional

import polars as pl
import pypsa

from model.parameters import (
    ScenarioParameters,
    calculate_annualised_capex,
    load_assumptions,
)


def build_lux_network(
    params: ScenarioParameters,
    assumptions_path: Path | str = "data/assumptions.yaml",
    demand_path: Path | str = "data/demand.csv",
    renewables_path: Path | str = "data/renewable_profiles.csv",
) -> pypsa.Network:
    """
    Build single-node PyPSA network for Luxembourg.

    Uses 168 representative hourly snapshots (one week) weighted to 8760 annual hours.
    Minimises annualised system cost subject to hourly demand balance and resource constraints.
    """
    assumptions = load_assumptions(assumptions_path)
    gen_cfg = assumptions["general"]
    tech_cfg = assumptions["technologies"]

    discount_rate = float(gen_cfg["discount_rate"])
    hours_in_year = float(gen_cfg["hours_in_year"])
    rep_hours = int(gen_cfg["representative_hours"])
    annual_weight = hours_in_year / rep_hours

    # 1. Load profiles using Polars
    df_demand = pl.read_csv(demand_path)
    df_renewables = pl.read_csv(renewables_path)

    if len(df_demand) != rep_hours or len(df_renewables) != rep_hours:
        raise ValueError(
            f"Expected {rep_hours} hourly snapshots, got demand={len(df_demand)}, renewables={len(df_renewables)}"
        )

    # Apply demand growth scenario multiplier
    demand_multiplier = 1.0 + (params.demand_growth_pct / 100.0)
    scaled_demand = (df_demand["demand_mw"] * demand_multiplier).to_list()

    solar_cf = df_renewables["solar_cf"].to_list()
    wind_cf = df_renewables["wind_cf"].to_list()

    # 2. Compute annualised capital costs (€/MW/year)
    solar_base_ann_capex = calculate_annualised_capex(
        overnight_capex=float(tech_cfg["solar"]["overnight_capex"]),
        lifetime_years=int(tech_cfg["solar"]["lifetime"]),
        discount_rate=discount_rate,
        fom_percent=float(tech_cfg["solar"]["fom_percent"]),
    )
    solar_scenario_ann_capex = solar_base_ann_capex * (params.solar_cost_mult_pct / 100.0)

    wind_base_ann_capex = calculate_annualised_capex(
        overnight_capex=float(tech_cfg["wind"]["overnight_capex"]),
        lifetime_years=int(tech_cfg["wind"]["lifetime"]),
        discount_rate=discount_rate,
        fom_percent=float(tech_cfg["wind"]["fom_percent"]),
    )
    wind_scenario_ann_capex = wind_base_ann_capex * (params.wind_cost_mult_pct / 100.0)

    # Battery capex: power component + energy component * duration
    battery_max_hours = float(tech_cfg["battery"]["max_hours"])
    bat_power_ann_capex = calculate_annualised_capex(
        overnight_capex=float(tech_cfg["battery"]["overnight_capex_power"]),
        lifetime_years=int(tech_cfg["battery"]["lifetime"]),
        discount_rate=discount_rate,
        fom_percent=float(tech_cfg["battery"]["fom_percent"]),
    )
    bat_energy_ann_capex = calculate_annualised_capex(
        overnight_capex=float(tech_cfg["battery"]["overnight_capex_energy"]),
        lifetime_years=int(tech_cfg["battery"]["lifetime"]),
        discount_rate=discount_rate,
        fom_percent=float(tech_cfg["battery"]["fom_percent"]),
    )
    battery_base_ann_capex = bat_power_ann_capex + (bat_energy_ann_capex * battery_max_hours)
    battery_scenario_ann_capex = battery_base_ann_capex * (params.battery_cost_mult_pct / 100.0)

    # Gas marginal cost: fuel cost / electrical efficiency + carbon price * CO2 factor
    gas_fuel_cost = float(tech_cfg["gas"]["fuel_cost"])
    gas_efficiency = float(tech_cfg["gas"]["efficiency"])
    gas_co2_factor = float(tech_cfg["gas"]["co2_emissions_factor"])
    gas_marginal_cost = (gas_fuel_cost / gas_efficiency) + (params.carbon_price * gas_co2_factor)

    # Gas capacity expansion capex (if extending beyond existing 400 MW)
    gas_ann_capex = calculate_annualised_capex(
        overnight_capex=float(tech_cfg["gas"]["overnight_capex"]),
        lifetime_years=int(tech_cfg["gas"]["lifetime"]),
        discount_rate=discount_rate,
        fom_percent=float(tech_cfg["gas"]["fom_percent"]),
    )

    # 3. Initialize PyPSA Network
    n = pypsa.Network()
    n.set_snapshots(range(rep_hours))
    # Crucial for storage physics vs annualised economics:
    # "stores" must be 1.0 hour (the physical time step elapsed per snapshot)
    # "generators" is 1.0 hour (physical energy per snapshot in MWh)
    # "objective" is annual_weight (scales operational costs to full 8760-hour annual economics)
    n.snapshot_weightings["stores"] = 1.0
    n.snapshot_weightings["generators"] = 1.0
    n.snapshot_weightings["objective"] = annual_weight

    # Add carriers
    n.add("Carrier", "AC")
    n.add("Carrier", "solar", co2_emissions=0.0, color="#f39c12")
    n.add("Carrier", "wind", co2_emissions=0.0, color="#2980b9")
    n.add("Carrier", "battery", co2_emissions=0.0, color="#8e44ad")
    n.add("Carrier", "gas", co2_emissions=gas_co2_factor, color="#e74c3c")
    n.add(
        "Carrier",
        "import",
        co2_emissions=float(tech_cfg["import"]["co2_emissions_factor"]),
        color="#34495e",
    )

    # Add single Luxembourg node
    n.add("Bus", "Luxembourg", carrier="AC")

    # Add electricity demand
    n.add("Load", "electricity_demand", bus="Luxembourg", p_set=scaled_demand)

    # Add Solar PV (optimisable capacity)
    n.add(
        "Generator",
        "solar",
        bus="Luxembourg",
        carrier="solar",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=float(tech_cfg["solar"]["max_potential_mw"]),
        p_max_pu=solar_cf,
        capital_cost=solar_scenario_ann_capex,
        marginal_cost=float(tech_cfg["solar"]["marginal_cost"]),
    )

    # Add Onshore Wind (optimisable capacity)
    n.add(
        "Generator",
        "wind",
        bus="Luxembourg",
        carrier="wind",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=float(tech_cfg["wind"]["max_potential_mw"]),
        p_max_pu=wind_cf,
        capital_cost=wind_scenario_ann_capex,
        marginal_cost=float(tech_cfg["wind"]["marginal_cost"]),
    )

    # Add Gas Backup (existing 400 MW + extendable up to 800 MW max)
    gas_existing = float(tech_cfg["gas"]["existing_capacity_mw"])
    gas_max = float(tech_cfg["gas"]["max_capacity_mw"])
    n.add(
        "Generator",
        "gas",
        bus="Luxembourg",
        carrier="gas",
        p_nom=gas_existing,
        p_nom_extendable=True,
        p_nom_min=gas_existing,
        p_nom_max=gas_max,
        capital_cost=gas_ann_capex,
        marginal_cost=gas_marginal_cost,
        efficiency=gas_efficiency,
    )

    # Add Electricity Imports (at adjustable price up to cross-border limit)
    import_capacity = float(tech_cfg["import"]["max_import_capacity_mw"])
    n.add(
        "Generator",
        "import",
        bus="Luxembourg",
        carrier="import",
        p_nom=import_capacity,
        p_nom_extendable=False,
        marginal_cost=params.import_price,
    )

    # Add Battery Storage (optimisable power and energy capacity)
    rt_efficiency = float(tech_cfg["battery"]["round_trip_efficiency"])
    half_efficiency = sqrt(rt_efficiency)
    n.add(
        "StorageUnit",
        "battery",
        bus="Luxembourg",
        carrier="battery",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=float(tech_cfg["battery"]["max_potential_mw"]),
        max_hours=battery_max_hours,
        efficiency_store=half_efficiency,
        efficiency_dispatch=half_efficiency,
        cyclic_state_of_charge=True,  # No free energy across period
        capital_cost=battery_scenario_ann_capex,
        marginal_cost=float(tech_cfg["battery"]["marginal_cost"]),
    )

    n.sanitize()
    return n
