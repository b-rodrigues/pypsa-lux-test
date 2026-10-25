"""
Unit tests for Polars-based results extraction, energy balance, and comparative sensitivities.
"""

import polars as pl
import pytest
from model.parameters import ScenarioParameters
from model.build_network import build_lux_network
from model.run_model import run_model
from model.results import extract_results


def test_results_polars_dataframes():
    """Verify that all extracted tables are valid Polars DataFrames with expected schemas."""
    params = ScenarioParameters.baseline()
    network = build_lux_network(params)
    run_res = run_model(network)
    assert run_res.success is True

    res = extract_results(network, params)

    # 1. Hourly Dispatch DataFrame
    assert isinstance(res.hourly_dispatch, pl.DataFrame)
    assert res.hourly_dispatch.shape[0] == 168
    expected_dispatch_cols = [
        "snapshot",
        "day",
        "hour",
        "demand_mw",
        "solar_mw",
        "wind_mw",
        "gas_mw",
        "import_mw",
        "battery_discharge_mw",
        "battery_charge_mw",
        "battery_soc_mwh",
        "net_generation_mw",
    ]
    for col in expected_dispatch_cols:
        assert col in res.hourly_dispatch.columns

    # 2. Capacities DataFrame
    assert isinstance(res.capacities, pl.DataFrame)
    assert "technology" in res.capacities.columns
    assert "capacity" in res.capacities.columns
    assert "unit" in res.capacities.columns

    # 3. Generation Mix DataFrame
    assert isinstance(res.generation_mix, pl.DataFrame)
    assert "technology" in res.generation_mix.columns
    assert "annual_generation_mwh" in res.generation_mix.columns
    assert "share_of_supply_pct" in res.generation_mix.columns

    # 4. Cost Breakdown DataFrame
    assert isinstance(res.cost_breakdown, pl.DataFrame)
    assert "capex_eur_per_year" in res.cost_breakdown.columns
    assert "opex_eur_per_year" in res.cost_breakdown.columns
    assert "total_eur_per_year" in res.cost_breakdown.columns


def test_carbon_price_sensitivity():
    """Verify that increasing carbon price penalises gas generation and lowers emissions."""
    # Low carbon price (€20/tCO2)
    p_low_co2 = ScenarioParameters(
        demand_growth_pct=0.0,
        solar_cost_mult_pct=100.0,
        wind_cost_mult_pct=100.0,
        battery_cost_mult_pct=100.0,
        import_price=100.0,
        carbon_price=20.0,
    )
    n_low = build_lux_network(p_low_co2)
    run_model(n_low)
    res_low = extract_results(n_low, p_low_co2)

    # High carbon price (€150/tCO2)
    p_high_co2 = ScenarioParameters(
        demand_growth_pct=0.0,
        solar_cost_mult_pct=100.0,
        wind_cost_mult_pct=100.0,
        battery_cost_mult_pct=100.0,
        import_price=100.0,
        carbon_price=150.0,
    )
    n_high = build_lux_network(p_high_co2)
    run_model(n_high)
    res_high = extract_results(n_high, p_high_co2)

    # Higher carbon price must not increase emissions
    assert res_high.annual_co2_emissions_t <= res_low.annual_co2_emissions_t


def test_demand_growth_sensitivity():
    """Verify that higher electricity demand increases total modelled system cost."""
    p_low_dem = ScenarioParameters(
        demand_growth_pct=-10.0,
        solar_cost_mult_pct=100.0,
        wind_cost_mult_pct=100.0,
        battery_cost_mult_pct=100.0,
        import_price=100.0,
        carbon_price=80.0,
    )
    n_low = build_lux_network(p_low_dem)
    run_model(n_low)
    res_low = extract_results(n_low, p_low_dem)

    p_high_dem = ScenarioParameters(
        demand_growth_pct=30.0,
        solar_cost_mult_pct=100.0,
        wind_cost_mult_pct=100.0,
        battery_cost_mult_pct=100.0,
        import_price=100.0,
        carbon_price=80.0,
    )
    n_high = build_lux_network(p_high_dem)
    run_model(n_high)
    res_high = extract_results(n_high, p_high_dem)

    assert res_high.total_annual_cost_eur > res_low.total_annual_cost_eur
    assert res_high.annual_demand_mwh > res_low.annual_demand_mwh
