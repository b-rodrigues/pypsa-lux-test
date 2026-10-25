"""
Unit tests for Luxembourg PyPSA model construction, parameter validation, and optimization.
"""

import pytest
from model.parameters import (
    ScenarioParameters,
    calculate_annualised_capex,
    calculate_annuitisation_factor,
    load_assumptions,
)
from model.build_network import build_lux_network
from model.run_model import run_model
from model.results import extract_results


def test_scenario_parameters_validation():
    """Verify that parameters enforce valid ranges and throw on invalid values."""
    baseline = ScenarioParameters.baseline()
    assert baseline.demand_growth_pct == 0.0
    assert baseline.import_price == 100.0
    assert baseline.carbon_price == 80.0

    # Test out-of-range parameters
    with pytest.raises(ValueError, match="Demand growth"):
        ScenarioParameters(demand_growth_pct=50.0)

    with pytest.raises(ValueError, match="Solar cost multiplier"):
        ScenarioParameters(solar_cost_mult_pct=10.0)

    with pytest.raises(ValueError, match="Wind cost multiplier"):
        ScenarioParameters(wind_cost_mult_pct=160.0)

    with pytest.raises(ValueError, match="Battery cost multiplier"):
        ScenarioParameters(battery_cost_mult_pct=250.0)

    with pytest.raises(ValueError, match="Import price"):
        ScenarioParameters(import_price=15.0)

    with pytest.raises(ValueError, match="Carbon price"):
        ScenarioParameters(carbon_price=-5.0)


def test_annuitisation_factor_formula():
    """Verify capital recovery factor math: r / (1 - (1+r)^-N)."""
    # 25 years at 5% discount rate
    crf = calculate_annuitisation_factor(lifetime_years=25, discount_rate=0.05)
    expected_crf = 0.05 / (1.0 - (1.05) ** (-25))
    assert pytest.approx(crf, rel=1e-5) == expected_crf
    assert pytest.approx(crf, abs=1e-3) == 0.07095

    # Annualised capex includes FOM
    ann_capex = calculate_annualised_capex(
        overnight_capex=1000.0,
        lifetime_years=25,
        discount_rate=0.05,
        fom_percent=0.02,
    )
    assert pytest.approx(ann_capex, abs=1e-2) == 1000.0 * (expected_crf + 0.02)


def test_load_assumptions():
    """Verify assumptions YAML file loads correctly."""
    assumptions = load_assumptions("data/assumptions.yaml")
    assert "general" in assumptions
    assert "technologies" in assumptions
    assert assumptions["general"]["representative_hours"] == 168
    assert "solar" in assumptions["technologies"]
    assert "wind" in assumptions["technologies"]
    assert "battery" in assumptions["technologies"]
    assert "gas" in assumptions["technologies"]
    assert "import" in assumptions["technologies"]


def test_network_optimization_baseline():
    """Verify that the baseline model solves to optimality and meets demand."""
    params = ScenarioParameters.baseline()
    network = build_lux_network(params)

    assert len(network.snapshots) == 168
    assert "Luxembourg" in network.buses.index
    assert "electricity_demand" in network.loads.index
    assert "solar" in network.generators.index
    assert "wind" in network.generators.index
    assert "gas" in network.generators.index
    assert "import" in network.generators.index
    assert "battery" in network.storage_units.index

    # Check snapshot weightings
    assert network.snapshot_weightings["stores"].iloc[0] == 1.0
    assert pytest.approx(network.snapshot_weightings["objective"].iloc[0], rel=1e-4) == (8760.0 / 168.0)

    # Solve with HiGHS
    result = run_model(network)
    assert result.success is True
    assert result.status == "ok"
    assert result.termination_condition in ["optimal", "locallyOptimal"]
    assert result.objective is not None
    assert result.objective > 0.0

    # Extract results and verify energy balance
    sim_res = extract_results(network, params)
    assert sim_res.energy_balance_max_error_mw < 1e-3
    assert sim_res.annual_demand_mwh > 6.0e6  # ~6.6 TWh
    assert sim_res.total_annual_cost_eur > 0.0
