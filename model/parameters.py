"""
Scenario parameters, cost annualisation, and assumptions loading for Luxembourg Energy Simulator.
All tabular transformations and data parsing are executed using Polars.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import yaml


@dataclass(frozen=True)
class ScenarioParameters:
    """User-controlled scenario parameters with strict bounds validation."""

    demand_growth_pct: float = 10.0  # -10% to +40%
    solar_cost_mult_pct: float = 60.0  # 20% to 150%
    wind_cost_mult_pct: float = 50.0  # 20% to 150%
    battery_cost_mult_pct: float = 120.0  # 20% to 200%
    import_price: float = 100.0  # €20 to €250 / MWh
    carbon_price: float = 80.0  # €0 to €200 / tCO2

    def __post_init__(self) -> None:
        """Validate parameter ranges according to the specification."""
        if not (-10.0 <= self.demand_growth_pct <= 40.0):
            raise ValueError(
                f"Demand growth ({self.demand_growth_pct}%) must be between -10% and +40%."
            )
        if not (20.0 <= self.solar_cost_mult_pct <= 150.0):
            raise ValueError(
                f"Solar cost multiplier ({self.solar_cost_mult_pct}%) must be between 20% and 150%."
            )
        if not (20.0 <= self.wind_cost_mult_pct <= 150.0):
            raise ValueError(
                f"Wind cost multiplier ({self.wind_cost_mult_pct}%) must be between 20% and 150%."
            )
        if not (20.0 <= self.battery_cost_mult_pct <= 200.0):
            raise ValueError(
                f"Battery cost multiplier ({self.battery_cost_mult_pct}%) must be between 20% and 200%."
            )
        if not (20.0 <= self.import_price <= 250.0):
            raise ValueError(
                f"Import price (€{self.import_price}/MWh) must be between €20 and €250/MWh."
            )
        if not (0.0 <= self.carbon_price <= 200.0):
            raise ValueError(
                f"Carbon price (€{self.carbon_price}/tCO2) must be between €0 and €200/tCO2."
            )

    @classmethod
    def baseline(cls) -> "ScenarioParameters":
        """Return the default baseline scenario parameters (0% growth, 100% baseline costs)."""
        return cls(
            demand_growth_pct=0.0,
            solar_cost_mult_pct=100.0,
            wind_cost_mult_pct=100.0,
            battery_cost_mult_pct=100.0,
            import_price=100.0,
            carbon_price=80.0,
        )


def calculate_annuitisation_factor(lifetime_years: int, discount_rate: float) -> float:
    """Calculate the capital recovery factor (CRF): r / (1 - (1 + r)^(-N))."""
    if discount_rate <= 0:
        return 1.0 / lifetime_years
    return discount_rate / (1.0 - (1.0 + discount_rate) ** (-lifetime_years))


def calculate_annualised_capex(
    overnight_capex: float,
    lifetime_years: int,
    discount_rate: float,
    fom_percent: float,
) -> float:
    """
    Calculate annualised capacity cost (€/MW/year) combining capital recovery and annual fixed O&M.
    """
    crf = calculate_annuitisation_factor(lifetime_years, discount_rate)
    return overnight_capex * (crf + fom_percent)


def load_assumptions(path: Path | str = "data/assumptions.yaml") -> Dict[str, Any]:
    """Load baseline techno-economic assumptions from YAML file."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Assumptions file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data
