"""
Extraction, annualisation, and validation of PyPSA optimization results.
All output data structures and tabular metrics are strictly managed using Polars.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
import polars as pl
import pypsa

from model.parameters import ScenarioParameters


@dataclass
class SimulationResults:
    """Comprehensive results container with Polars DataFrames and summary indicators."""

    parameters: ScenarioParameters
    total_annual_cost_eur: float
    annual_demand_mwh: float
    annual_co2_emissions_t: float
    import_share_pct: float
    renewable_share_pct: float
    hourly_dispatch: pl.DataFrame
    capacities: pl.DataFrame
    generation_mix: pl.DataFrame
    cost_breakdown: pl.DataFrame
    energy_balance_max_error_mw: float


def extract_results(
    network: pypsa.Network,
    params: ScenarioParameters,
    day_names: List[str] | None = None,
) -> SimulationResults:
    """
    Extract, annualise, and validate results from an optimised PyPSA network.

    Constructs clean Polars DataFrames for hourly dispatch, capacities, generation mix,
    and cost breakdowns. Performs hourly energy balance validation.
    """
    if day_names is None:
        raw_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_names = [raw_days[h // 24] for h in range(168)]

    # Annual weighting: 8760 / 168 = 52.142857...
    annual_weight = 8760.0 / len(network.snapshots)

    # 1. Hourly time series extraction
    snapshots = list(range(len(network.snapshots)))
    hours = [s % 24 for s in snapshots]

    # Load demand (MW)
    demand_mw = [float(v) for v in network.loads_t.p["electricity_demand"].values]

    # Generation dispatch (MW)
    solar_mw = [float(max(0.0, v)) for v in network.generators_t.p["solar"].values]
    wind_mw = [float(max(0.0, v)) for v in network.generators_t.p["wind"].values]
    gas_mw = [float(max(0.0, v)) for v in network.generators_t.p["gas"].values]
    import_mw = [float(max(0.0, v)) for v in network.generators_t.p["import"].values]

    # Battery dispatch and storage (StorageUnit convention: >0 dispatch, <0 charging)
    bat_p = [float(v) for v in network.storage_units_t.p["battery"].values]
    bat_discharge_mw = [max(0.0, p) for p in bat_p]
    bat_charge_mw = [max(0.0, -p) for p in bat_p]
    bat_soc_mwh = [
        float(v) for v in network.storage_units_t.state_of_charge["battery"].values
    ]

    # Energy balance verification for each snapshot
    balance_errors = [
        abs((s + w + g + imp + dis) - (dem + chg))
        for s, w, g, imp, dis, dem, chg in zip(
            solar_mw,
            wind_mw,
            gas_mw,
            import_mw,
            bat_discharge_mw,
            demand_mw,
            bat_charge_mw,
        )
    ]
    max_balance_error = max(balance_errors)
    if max_balance_error > 0.1:  # 0.1 MW tolerance
        raise ValueError(
            f"Energy balance check failed! Max imbalance: {max_balance_error:.4f} MW."
        )

    # Construct Hourly Dispatch Polars DataFrame
    hourly_dispatch_df = pl.DataFrame(
        {
            "snapshot": snapshots,
            "day": day_names,
            "hour": hours,
            "demand_mw": demand_mw,
            "solar_mw": solar_mw,
            "wind_mw": wind_mw,
            "gas_mw": gas_mw,
            "import_mw": import_mw,
            "battery_discharge_mw": bat_discharge_mw,
            "battery_charge_mw": bat_charge_mw,
            "battery_soc_mwh": bat_soc_mwh,
            "net_generation_mw": [
                s + w + g + imp + dis - chg
                for s, w, g, imp, dis, chg in zip(
                    solar_mw,
                    wind_mw,
                    gas_mw,
                    import_mw,
                    bat_discharge_mw,
                    bat_charge_mw,
                )
            ],
        }
    )

    # 2. Capacities Polars DataFrame
    solar_cap_mw = float(network.generators.loc["solar", "p_nom_opt"])
    wind_cap_mw = float(network.generators.loc["wind", "p_nom_opt"])
    gas_cap_mw = float(network.generators.loc["gas", "p_nom_opt"])
    import_cap_mw = float(network.generators.loc["import", "p_nom"])
    battery_power_mw = float(network.storage_units.loc["battery", "p_nom_opt"])
    battery_hours = float(network.storage_units.loc["battery", "max_hours"])
    battery_energy_mwh = battery_power_mw * battery_hours

    capacities_df = pl.DataFrame(
        {
            "technology": [
                "Solar PV",
                "Onshore Wind",
                "Battery Storage (Power)",
                "Battery Storage (Energy)",
                "Gas Generation",
                "Interconnectors (Import)",
            ],
            "carrier": ["solar", "wind", "battery", "battery", "gas", "import"],
            "capacity": [
                solar_cap_mw,
                wind_cap_mw,
                battery_power_mw,
                battery_energy_mwh,
                gas_cap_mw,
                import_cap_mw,
            ],
            "unit": ["MW", "MW", "MW", "MWh", "MW", "MW"],
        }
    )

    # 3. Generation Mix & Annual Totals
    solar_annual_mwh = sum(solar_mw) * annual_weight
    wind_annual_mwh = sum(wind_mw) * annual_weight
    gas_annual_mwh = sum(gas_mw) * annual_weight
    import_annual_mwh = sum(import_mw) * annual_weight
    bat_discharge_annual_mwh = sum(bat_discharge_mw) * annual_weight
    bat_charge_annual_mwh = sum(bat_charge_mw) * annual_weight
    demand_annual_mwh = sum(demand_mw) * annual_weight

    total_supplied_mwh = (
        solar_annual_mwh + wind_annual_mwh + gas_annual_mwh + import_annual_mwh
    )
    if total_supplied_mwh == 0:
        total_supplied_mwh = 1.0

    generation_mix_df = pl.DataFrame(
        {
            "technology": [
                "Solar PV",
                "Onshore Wind",
                "Gas Generation",
                "Electricity Imports",
                "Battery Discharge",
                "Battery Charge",
            ],
            "carrier": ["solar", "wind", "gas", "import", "battery", "battery"],
            "annual_generation_mwh": [
                solar_annual_mwh,
                wind_annual_mwh,
                gas_annual_mwh,
                import_annual_mwh,
                bat_discharge_annual_mwh,
                bat_charge_annual_mwh,
            ],
            "annual_generation_gwh": [
                solar_annual_mwh / 1000.0,
                wind_annual_mwh / 1000.0,
                gas_annual_mwh / 1000.0,
                import_annual_mwh / 1000.0,
                bat_discharge_annual_mwh / 1000.0,
                bat_charge_annual_mwh / 1000.0,
            ],
            "share_of_supply_pct": [
                (solar_annual_mwh / total_supplied_mwh) * 100.0,
                (wind_annual_mwh / total_supplied_mwh) * 100.0,
                (gas_annual_mwh / total_supplied_mwh) * 100.0,
                (import_annual_mwh / total_supplied_mwh) * 100.0,
                (bat_discharge_annual_mwh / total_supplied_mwh) * 100.0,
                (bat_charge_annual_mwh / total_supplied_mwh) * 100.0,
            ],
        }
    )

    # 4. Emissions and Import Dependence
    gas_co2_factor = float(network.carriers.loc["gas", "co2_emissions"])
    import_co2_factor = float(network.carriers.loc["import", "co2_emissions"])
    annual_co2_t = (
        (gas_annual_mwh * gas_co2_factor) + (import_annual_mwh * import_co2_factor)
    )
    import_share_pct = (import_annual_mwh / demand_annual_mwh) * 100.0
    renewable_share_pct = (
        (solar_annual_mwh + wind_annual_mwh) / demand_annual_mwh
    ) * 100.0

    # 5. Cost Breakdown (€/year)
    solar_ann_capex = solar_cap_mw * float(
        network.generators.loc["solar", "capital_cost"]
    )
    solar_ann_opex = solar_annual_mwh * float(
        network.generators.loc["solar", "marginal_cost"]
    )

    wind_ann_capex = wind_cap_mw * float(network.generators.loc["wind", "capital_cost"])
    wind_ann_opex = wind_annual_mwh * float(
        network.generators.loc["wind", "marginal_cost"]
    )

    gas_ann_capex = (gas_cap_mw - 400.0) * float(
        network.generators.loc["gas", "capital_cost"]
    )
    gas_ann_capex = max(0.0, gas_ann_capex)
    gas_ann_opex = gas_annual_mwh * float(network.generators.loc["gas", "marginal_cost"])

    import_ann_capex = 0.0
    import_ann_opex = import_annual_mwh * float(
        network.generators.loc["import", "marginal_cost"]
    )

    bat_ann_capex = battery_power_mw * float(
        network.storage_units.loc["battery", "capital_cost"]
    )
    bat_ann_opex = bat_discharge_annual_mwh * float(
        network.storage_units.loc["battery", "marginal_cost"]
    )

    cost_breakdown_df = pl.DataFrame(
        {
            "technology": [
                "Solar PV",
                "Onshore Wind",
                "Gas Generation",
                "Electricity Imports",
                "Battery Storage",
                "Total System",
            ],
            "capex_eur_per_year": [
                solar_ann_capex,
                wind_ann_capex,
                gas_ann_capex,
                import_ann_capex,
                bat_ann_capex,
                solar_ann_capex
                + wind_ann_capex
                + gas_ann_capex
                + import_ann_capex
                + bat_ann_capex,
            ],
            "opex_eur_per_year": [
                solar_ann_opex,
                wind_ann_opex,
                gas_ann_opex,
                import_ann_opex,
                bat_ann_opex,
                solar_ann_opex
                + wind_ann_opex
                + gas_ann_opex
                + import_ann_opex
                + bat_ann_opex,
            ],
            "total_eur_per_year": [
                solar_ann_capex + solar_ann_opex,
                wind_ann_capex + wind_ann_opex,
                gas_ann_capex + gas_ann_opex,
                import_ann_capex + import_ann_opex,
                bat_ann_capex + bat_ann_opex,
                solar_ann_capex
                + solar_ann_opex
                + wind_ann_capex
                + wind_ann_opex
                + gas_ann_capex
                + gas_ann_opex
                + import_ann_capex
                + import_ann_opex
                + bat_ann_capex
                + bat_ann_opex,
            ],
        }
    )

    return SimulationResults(
        parameters=params,
        total_annual_cost_eur=float(network.objective),
        annual_demand_mwh=demand_annual_mwh,
        annual_co2_emissions_t=annual_co2_t,
        import_share_pct=import_share_pct,
        renewable_share_pct=renewable_share_pct,
        hourly_dispatch=hourly_dispatch_df,
        capacities=capacities_df,
        generation_mix=generation_mix_df,
        cost_breakdown=cost_breakdown_df,
        energy_balance_max_error_mw=max_balance_error,
    )
