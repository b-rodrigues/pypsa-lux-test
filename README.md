# Luxembourg Energy Transition Simulator 🇱🇺

An interactive electricity system optimisation simulator and decision-support prototype for Luxembourg, pairing **PyPSA** (Python for Power System Analysis) and the **HiGHS** solver with **Shiny for Python** and **Polars**.

Built as an interactive proof of concept for **STATEC** and energy decision-makers to evaluate scenarios, trade-offs, and cost-optimal electricity system configurations in real time.

---

## Key Features

- **Single-Node Optimization Engine**: PyPSA linear programming model solving least-cost investment and hourly dispatch in <0.05 seconds with HiGHS.
- **Representative-Week Time Dimension**: 168 hourly snapshots (weekdays vs weekends, midday solar peak, morning/evening ramps) annualised to 8,760 hours ($52.14\times$ weighting).
- **6 Interactive Scenario Controls**:
  - Electricity demand growth: $-10\%$ to $+40\%$ (default $+10\%$)
  - Solar PV investment cost: $20\%$ to $150\%$ of baseline (default $60\%$)
  - Onshore wind investment cost: $20\%$ to $150\%$ of baseline (default $50\%$)
  - 4h battery storage investment cost: $20\%$ to $200\%$ of baseline (default $120\%$)
  - Import wholesale electricity price: €20 to €250 / MWh (default €100 / MWh)
  - Carbon price: €0 to €200 / $\text{tCO}_2$ (default €80 / $\text{tCO}_2$)
- **Rich Dashboard**:
  - Live baseline vs scenario KPI comparisons (Annual system cost, $\text{CO}_2$ emissions, import dependency, renewable share).
  - Stacked annual generation mix (GWh/year) & optimal installed capacities (MW).
  - 168-hour representative week interactive dispatch and battery state of charge.
  - Interactive Polars data tables and methodology documentation.
- **Data Pipeline**: 100% **Polars** for tabular transformations, data parsing, and metrics.
- **Hermetic & Reproducible**: Fully managed with **Nix Flake** (Nixpkgs, no uv/pip reliance).

---

## Project Structure

```
.
├── flake.nix               # Nix flake providing Python, Shiny, Polars, PyPSA, HiGHS
├── flake.lock              # Pinned reproducible dependency lock
├── pyproject.toml          # Tooling and pytest configuration
├── requirements.txt        # Package reference list
├── app.py                  # Shiny for Python web interface and reactive server
├── model/
│   ├── __init__.py         # Package exports
│   ├── parameters.py       # Parameter validation and annuitisation math
│   ├── build_network.py    # PyPSA network construction and snapshot weighting
│   ├── run_model.py        # HiGHS solver execution and error handling
│   └── results.py          # Results extraction, annualisation, and Polars DataFrames
├── data/
│   ├── assumptions.yaml    # Baseline techno-economic parameters
│   ├── demand.csv          # 168-hour baseline Luxembourg demand profile
│   └── renewable_profiles.csv # 168-hour solar PV and onshore wind capacity factors
├── tests/
│   ├── test_model.py       # Parameters, annuitisation, network solve tests
│   └── test_results.py     # Energy balance, Polars schemas, sensitivity tests
└── README.md
```

---

## Quickstart

### 1. Enter the Nix Development Shell

Ensure Nix with Flakes is available, then enter the shell:

```bash
nix develop
```

This immediately loads Python, Shiny, Polars, PyPSA, Linopy, and the HiGHS solver.

### 2. Launch the Shiny Dashboard

```bash
shiny run app.py --reload
```

Open your browser at `http://127.0.0.1:8000`.

### 3. Run the Automated Test Suite

```bash
pytest
```

---

## Mathematical Formulation

The simulator minimises the annualised system cost:

$$\min \quad \sum_{g \in \mathcal{G}} C_{\text{ann\_capex}, g} \cdot P_{\text{nom}, g} + \sum_{t=0}^{167} w_{\text{ann}} \cdot \left( \sum_{g \in \mathcal{G}} c_{\text{marg}, g} \cdot p_{g,t} + c_{\text{bat\_marg}} \cdot p_{\text{bat\_dis}, t} \right)$$

subject to:

1. **Hourly Supply-Demand Balance**:
   $$p_{\text{solar}, t} + p_{\text{wind}, t} + p_{\text{gas}, t} + p_{\text{import}, t} + p_{\text{bat\_dis}, t} - p_{\text{bat\_chg}, t} = D_t \quad \forall t \in \{0, \dots, 167\}$$

2. **Renewable Availability Limits**:
   $$0 \le p_{\text{solar}, t} \le P_{\text{nom, solar}} \cdot \text{CF}_{\text{solar}, t}, \quad 0 \le p_{\text{wind}, t} \le P_{\text{nom, wind}} \cdot \text{CF}_{\text{wind}, t}$$

3. **Storage State of Charge & Efficiency**:
   $$\text{SOC}_{t+1} = \text{SOC}_t + \eta_{\text{store}} \cdot p_{\text{bat\_chg}, t} - \frac{1}{\eta_{\text{dispatch}}} \cdot p_{\text{bat\_dis}, t}$$
   $$\text{SOC}_0 = \text{SOC}_{168} \quad \text{(cyclic condition: no unearned energy)}$$

4. **Capital Cost Annuitisation**:
   $$\text{CRF} = \frac{r}{1 - (1+r)^{-N}}, \quad C_{\text{ann\_capex}} = \text{CAPEX}_{\text{overnight}} \cdot (\text{CRF} + \text{FOM}_{\%})$$

---

## Quality & Validation Checks

- **Energy Balance Validation**: Verified that supply strictly matches demand for all 168 snapshots ($|\text{imbalance}| < 10^{-4}$ MW).
- **Physical Battery Conservation**: Round-trip efficiency ($88\%$) verified across charging and discharging throughput; cyclic initial/final boundary prevents artificial energy creation.
- **Fail-Safe Solver Integration**: Failed or infeasible runs display explicit error banners and preserve the previous valid solution, ensuring users are never shown partial or corrupted outputs.

---

## Framing to STATEC

*Luxembourg Energy Transition Simulator — An Interactive Proof of Concept*

This prototype uses open-source optimisation tooling (PyPSA) and modern interactive data interfaces (Shiny for Python + Polars) to demonstrate how long-term scenario modelling can be made transparent, intuitive, and interactive for analysts and policymakers. It is intended to explore directional trade-offs rather than replace calibrated official forecasts.
