"""
Luxembourg Energy Transition Simulator
Interactive Decision-Support Tool built with Shiny for Python, PyPSA, and Polars.
"""

from typing import Dict, Any, Tuple
import polars as pl
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from shiny import App, reactive, render, ui

from model.parameters import ScenarioParameters
from model.build_network import build_lux_network
from model.run_model import run_model
from model.results import SimulationResults, extract_results

# Precompute baseline results on startup
BASELINE_PARAMS = ScenarioParameters.baseline()
BASELINE_NETWORK = build_lux_network(BASELINE_PARAMS)
BASELINE_RUN = run_model(BASELINE_NETWORK)
if not BASELINE_RUN.success:
    raise RuntimeError(f"Baseline model failed to solve: {BASELINE_RUN.error_message}")
BASELINE_RESULTS: SimulationResults = extract_results(BASELINE_NETWORK, BASELINE_PARAMS)

CARRIER_COLORS = {
    "solar": "#f39c12",  # Amber
    "wind": "#2980b9",  # Steel Blue
    "gas": "#e74c3c",  # Crimson/Coral
    "import": "#34495e",  # Slate Navy
    "battery": "#8e44ad",  # Purple
}

# --- Shiny UI Definition ---
app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.title("Luxembourg Energy Transition Simulator"),
        ui.tags.script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"),
        ui.tags.style(
            """
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; }
            .kpi-card { background: white; border-radius: 8px; padding: 16px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .kpi-title { font-size: 0.825rem; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; }
            .kpi-value { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin-top: 4px; }
            .kpi-delta { font-size: 0.875rem; font-weight: 600; margin-top: 4px; }
            .kpi-delta.good { color: #16a34a; }
            .kpi-delta.bad { color: #dc2626; }
            .kpi-delta.neutral { color: #64748b; }
            .chart-card { background: white; border-radius: 8px; padding: 18px; border: 1px solid #e2e8f0; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .sidebar-title { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-bottom: 4px; }
            .sidebar-subtitle { font-size: 0.8rem; color: #64748b; margin-bottom: 16px; }
            .nav-tabs .nav-link { font-weight: 600; color: #475569; }
            .nav-tabs .nav-link.active { color: #0284c7; border-bottom: 2px solid #0284c7; }
            .alert-disclaimer { background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; margin-bottom: 16px; border-radius: 4px; font-size: 0.85rem; color: #1e3a8a; }
            """
        ),
    ),
    ui.div(
        {"class": "container-fluid py-3"},
        # Header banner
        ui.div(
            {"class": "d-flex justify-content-between align-items-center mb-3 pb-2 border-bottom"},
            ui.div(
                ui.h2("🇱🇺 Luxembourg Energy Transition Simulator", class_="h3 mb-1 fw-bold text-dark"),
                ui.p(
                    "Interactive single-node electricity system optimisation proof-of-concept powered by PyPSA & Polars",
                    class_="text-muted mb-0 small",
                ),
            ),
            ui.div(
                ui.span(
                    "Proof of Concept • HiGHS Solver",
                    class_="badge bg-light text-secondary border px-3 py-2 fs-6",
                )
            ),
        ),
        ui.layout_sidebar(
            # Sidebar controls
            ui.sidebar(
                ui.div(
                    ui.div("Scenario Assumptions", class_="sidebar-title"),
                    ui.div("Adjust parameters & re-optimise", class_="sidebar-subtitle"),
                ),
                ui.input_slider(
                    "demand_growth_pct",
                    "Electricity Demand Growth (%)",
                    min=-10.0,
                    max=40.0,
                    value=10.0,
                    step=1.0,
                    post="%",
                ),
                ui.input_slider(
                    "solar_cost_mult_pct",
                    "Solar Investment Cost (% of baseline)",
                    min=20.0,
                    max=150.0,
                    value=60.0,
                    step=5.0,
                    post="%",
                ),
                ui.input_slider(
                    "wind_cost_mult_pct",
                    "Wind Investment Cost (% of baseline)",
                    min=20.0,
                    max=150.0,
                    value=50.0,
                    step=5.0,
                    post="%",
                ),
                ui.input_slider(
                    "battery_cost_mult_pct",
                    "Battery Investment Cost (% of baseline)",
                    min=20.0,
                    max=200.0,
                    value=120.0,
                    step=5.0,
                    post="%",
                ),
                ui.input_slider(
                    "import_price",
                    "Import Electricity Price (€/MWh)",
                    min=20.0,
                    max=250.0,
                    value=100.0,
                    step=5.0,
                    pre="€",
                ),
                ui.input_slider(
                    "carbon_price",
                    "Carbon Price (€/tCO₂)",
                    min=0.0,
                    max=200.0,
                    value=80.0,
                    step=5.0,
                    pre="€",
                ),
                ui.input_action_button(
                    "run_btn",
                    "⚡ Run Scenario",
                    class_="btn btn-primary w-100 fw-bold py-2 mt-2 shadow-sm",
                ),
                ui.input_action_button(
                    "reset_btn",
                    "↺ Reset to Baseline",
                    class_="btn btn-outline-secondary w-100 mt-2 btn-sm",
                ),
                ui.hr(class_="my-3"),
                ui.div(
                    ui.div("Quick Presets:", class_="fw-bold text-muted small mb-2"),
                    ui.div(
                        {"class": "d-grid gap-1"},
                        ui.input_action_button(
                            "preset_renewables",
                            "☀️ Deep Decarbonisation",
                            class_="btn btn-outline-primary btn-sm text-start",
                        ),
                        ui.input_action_button(
                            "preset_electrification",
                            "📈 High Electrification (+30%)",
                            class_="btn btn-outline-primary btn-sm text-start",
                        ),
                        ui.input_action_button(
                            "preset_high_import",
                            "⚡ Import Crisis (€180/MWh)",
                            class_="btn btn-outline-primary btn-sm text-start",
                        ),
                    ),
                ),
                width=320,
            ),
            # Main Content Tabs
            ui.navset_tab(
                ui.nav_panel(
                    "Overview & Comparison",
                    ui.output_ui("error_banner"),
                    # KPI Cards
                    ui.div(
                        {"class": "row g-3 mb-4 mt-1"},
                        ui.div({"class": "col-12 col-sm-6 col-xl-3"}, ui.output_ui("kpi_cost")),
                        ui.div({"class": "col-12 col-sm-6 col-xl-3"}, ui.output_ui("kpi_emissions")),
                        ui.div({"class": "col-12 col-sm-6 col-xl-3"}, ui.output_ui("kpi_import_share")),
                        ui.div({"class": "col-12 col-sm-6 col-xl-3"}, ui.output_ui("kpi_renewables")),
                    ),
                    # Charts row 1: Generation Mix & Capacities
                    ui.div(
                        {"class": "row g-3 mb-3"},
                        ui.div(
                            {"class": "col-12 col-lg-6"},
                            ui.div(
                                {"class": "chart-card"},
                                ui.h5("Annual Generation Mix (GWh / year)", class_="fw-bold mb-3"),
                                ui.output_ui("plot_generation_mix"),
                            ),
                        ),
                        ui.div(
                            {"class": "col-12 col-lg-6"},
                            ui.div(
                                {"class": "chart-card"},
                                ui.h5("Optimal Installed Capacities (MW)", class_="fw-bold mb-3"),
                                ui.output_ui("plot_capacities"),
                            ),
                        ),
                    ),
                    # Charts row 2: Cost Breakdown
                    ui.div(
                        {"class": "row g-3"},
                        ui.div(
                            {"class": "col-12"},
                            ui.div(
                                {"class": "chart-card"},
                                ui.h5("Annual System Cost Breakdown (€M / year: Capex vs Opex)", class_="fw-bold mb-3"),
                                ui.output_ui("plot_cost_breakdown"),
                            ),
                        ),
                    ),
                ),
                ui.nav_panel(
                    "Hourly Dispatch",
                    ui.div(
                        {"class": "chart-card mt-3"},
                        ui.div(
                            {"class": "d-flex justify-content-between align-items-center mb-2"},
                            ui.h5("Representative Week Electricity Balance (168 Hours)", class_="fw-bold mb-0"),
                            ui.span("Supply strictly matches demand every hour", class_="text-muted small"),
                        ),
                        ui.p(
                            "Stacked areas represent generation and battery dispatch; the black curve indicates total hourly consumption. Negative areas below zero depict battery charging.",
                            class_="text-muted small mb-3",
                        ),
                        ui.output_ui("plot_dispatch"),
                    ),
                    ui.div(
                        {"class": "row g-3"},
                        ui.div(
                            {"class": "col-12 col-lg-6"},
                            ui.div(
                                {"class": "chart-card"},
                                ui.h6("Battery Storage State of Charge (MWh)", class_="fw-bold mb-2"),
                                ui.output_ui("plot_battery_soc"),
                            ),
                        ),
                        ui.div(
                            {"class": "col-12 col-lg-6"},
                            ui.div(
                                {"class": "chart-card"},
                                ui.h6("Daily Generation Profiling", class_="fw-bold mb-2"),
                                ui.output_ui("plot_daily_profile"),
                            ),
                        ),
                    ),
                ),
                ui.nav_panel(
                    "Data Tables (Polars)",
                    ui.div(
                        {"class": "chart-card mt-3"},
                        ui.h5("Optimal System Capacities", class_="fw-bold mb-3"),
                        ui.output_table("table_capacities"),
                    ),
                    ui.div(
                        {"class": "chart-card mt-3"},
                        ui.h5("Annual Generation Mix & Shares", class_="fw-bold mb-3"),
                        ui.output_table("table_generation_mix"),
                    ),
                    ui.div(
                        {"class": "chart-card mt-3"},
                        ui.h5("System Cost Accounting (€/year)", class_="fw-bold mb-3"),
                        ui.output_table("table_costs"),
                    ),
                ),
                ui.nav_panel(
                    "Methodology & Assumptions",
                    ui.div(
                        {"class": "chart-card mt-3"},
                        ui.div(
                            {"class": "alert-disclaimer"},
                            ui.strong("Disclaimer for STATEC & Decision-Makers: "),
                            "This interactive tool is a conceptual prototype demonstrating how open-source electricity system optimisation (PyPSA) can be paired with modern interactive interfaces (Shiny for Python & Polars). The model uses a single-node representation of Luxembourg with an hourly representative week. It is designed to explore directional trade-offs and sensitivity dynamics, rather than to serve as an official macro-energy forecast.",
                        ),
                        ui.h5("1. Optimization Formulation", class_="fw-bold mt-4"),
                        ui.p(
                            "The simulator solves a linear least-cost dispatch and investment optimisation problem using the HiGHS solver:"
                        ),
                        ui.tags.pre(
                            "min  Cost = Σ (Annualised_CAPEX_g * Capacity_g) + Σ_t (Annual_Weight * Marginal_Cost_g * Dispatch_{g,t})\n"
                            "s.t. Supply meets Demand for all t ∈ {0, ..., 167}\n"
                            "     Dispatch_{solar,t} ≤ Capacity_solar * Solar_CF_t\n"
                            "     Dispatch_{wind,t}  ≤ Capacity_wind  * Wind_CF_t\n"
                            "     Battery SOC_{t+1}   = Battery SOC_t + η_chg * Charge_t - (1/η_dis) * Discharge_t\n"
                            "     Battery SOC_0       = Battery SOC_168  (cyclic energy conservation)\n"
                            "     Import_{t}          ≤ Interconnector_Limit"
                        ),
                        ui.h5("2. Technology & Cost Conventions", class_="fw-bold mt-4"),
                        ui.tags.ul(
                            ui.tags.li(
                                ui.strong("Solar PV: "),
                                "Baseline overnight CAPEX of €650,000/MW (blend of commercial rooftop and utility/agrivoltaic), 25-year lifetime, 1.5% fixed O&M/year, discount rate 5% (WACC). Technical maximum potential: 2,000 MW.",
                            ),
                            ui.tags.li(
                                ui.strong("Onshore Wind: "),
                                "Baseline overnight CAPEX of €1,350,000/MW, 25-year lifetime, 2.5% fixed O&M/year, discount rate 5%. Land-use constrained maximum potential: 800 MW.",
                            ),
                            ui.tags.li(
                                ui.strong("Battery Storage: "),
                                "4-hour utility lithium-ion battery system (€160k/MW power + €180k/MWh energy), 15-year lifetime, 88% round-trip efficiency, cyclic state of charge constraint ensuring zero net unearned energy.",
                            ),
                            ui.tags.li(
                                ui.strong("Gas Backup: "),
                                "400 MW existing dispatchable thermal capacity with sunk capital cost; expandable up to 800 MW with new-build CAPEX. Marginal fuel cost €36/MWh_thermal at 52% electrical efficiency (~€69.2/MWh_el) plus the effective carbon price (€/tCO₂ * 0.38 tCO₂/MWh_el).",
                            ),
                            ui.tags.li(
                                ui.strong("Electricity Imports: "),
                                "1,400 MW cross-border transmission interconnector limit (representing Creos grid connections with Germany, Belgium, and France) at an adjustable wholesale import price with average grid intensity of 0.20 tCO₂/MWh.",
                            ),
                        ),
                        ui.h5("3. Representative Time Horizon", class_="fw-bold mt-4"),
                        ui.p(
                            "A 168-hour representative week (hourly snapshots) is weighted by 8760 / 168 = 52.142857 to scale energy balances and operational costs to annual totals. This preserves diurnal profiles (weekdays vs weekends, midday solar peak, morning/evening demand peaks) while solving in a fraction of a second."
                        ),
                    ),
                ),
            ),
        ),
    ),
)


# --- Shiny Server Logic ---
def server(input, output, session):
    # Current active scenario results
    current_results = reactive.Value(BASELINE_RESULTS)
    last_error = reactive.Value(None)

    # Preset handlers
    @reactive.Effect
    @reactive.event(input.preset_renewables)
    def _apply_preset_renewables():
        ui.update_slider("demand_growth_pct", value=15.0)
        ui.update_slider("solar_cost_mult_pct", value=35.0)
        ui.update_slider("wind_cost_mult_pct", value=40.0)
        ui.update_slider("battery_cost_mult_pct", value=50.0)
        ui.update_slider("import_price", value=140.0)
        ui.update_slider("carbon_price", value=140.0)

    @reactive.Effect
    @reactive.event(input.preset_electrification)
    def _apply_preset_electrification():
        ui.update_slider("demand_growth_pct", value=30.0)
        ui.update_slider("solar_cost_mult_pct", value=50.0)
        ui.update_slider("wind_cost_mult_pct", value=50.0)
        ui.update_slider("battery_cost_mult_pct", value=80.0)
        ui.update_slider("import_price", value=110.0)
        ui.update_slider("carbon_price", value=90.0)

    @reactive.Effect
    @reactive.event(input.preset_high_import)
    def _apply_preset_high_import():
        ui.update_slider("demand_growth_pct", value=5.0)
        ui.update_slider("solar_cost_mult_pct", value=60.0)
        ui.update_slider("wind_cost_mult_pct", value=60.0)
        ui.update_slider("battery_cost_mult_pct", value=70.0)
        ui.update_slider("import_price", value=180.0)
        ui.update_slider("carbon_price", value=100.0)

    @reactive.Effect
    @reactive.event(input.reset_btn)
    def _reset_to_baseline():
        ui.update_slider("demand_growth_pct", value=0.0)
        ui.update_slider("solar_cost_mult_pct", value=100.0)
        ui.update_slider("wind_cost_mult_pct", value=100.0)
        ui.update_slider("battery_cost_mult_pct", value=100.0)
        ui.update_slider("import_price", value=100.0)
        ui.update_slider("carbon_price", value=80.0)
        current_results.set(BASELINE_RESULTS)
        last_error.set(None)

    # Optimization trigger
    @reactive.Effect
    @reactive.event(input.run_btn)
    def _optimize_scenario():
        try:
            params = ScenarioParameters(
                demand_growth_pct=float(input.demand_growth_pct()),
                solar_cost_mult_pct=float(input.solar_cost_mult_pct()),
                wind_cost_mult_pct=float(input.wind_cost_mult_pct()),
                battery_cost_mult_pct=float(input.battery_cost_mult_pct()),
                import_price=float(input.import_price()),
                carbon_price=float(input.carbon_price()),
            )

            # Build and solve
            network = build_lux_network(params)
            run_res = run_model(network)

            if not run_res.success:
                last_error.set(run_res.error_message or "Optimization failed.")
                return

            # Extract results with Polars
            res = extract_results(network, params)
            current_results.set(res)
            last_error.set(None)

        except Exception as exc:
            last_error.set(str(exc))

    # Error alert display
    @render.ui
    def error_banner():
        err = last_error()
        if not err:
            return ui.div()
        return ui.div(
            {"class": "alert alert-danger alert-dismissible fade show mt-2 mb-3", "role": "alert"},
            ui.strong("Optimization Error: "),
            err,
        )

    # --- KPI Cards ---
    @render.ui
    def kpi_cost():
        res = current_results()
        base_cost = BASELINE_RESULTS.total_annual_cost_eur / 1e6
        scen_cost = res.total_annual_cost_eur / 1e6
        diff_pct = ((scen_cost - base_cost) / base_cost) * 100.0
        diff_abs = scen_cost - base_cost

        delta_cls = "good" if diff_abs <= 0 else "bad"
        sign = "+" if diff_abs > 0 else ""
        delta_str = f"{sign}{diff_pct:.1f}% ({sign}€{diff_abs:.1f}M/yr)" if abs(diff_abs) >= 0.05 else "Baseline"

        return ui.div(
            {"class": "kpi-card"},
            ui.div("Total Annual System Cost", class_="kpi-title"),
            ui.div(f"€{scen_cost:.1f} M", class_="kpi-value"),
            ui.div(f"{delta_str} vs baseline", class_=f"kpi-delta {delta_cls}"),
        )

    @render.ui
    def kpi_emissions():
        res = current_results()
        base_emi = BASELINE_RESULTS.annual_co2_emissions_t / 1e3
        scen_emi = res.annual_co2_emissions_t / 1e3
        diff_pct = ((scen_emi - base_emi) / base_emi) * 100.0 if base_emi > 0 else 0.0
        diff_abs = scen_emi - base_emi

        delta_cls = "good" if diff_abs <= 0 else "bad"
        sign = "+" if diff_abs > 0 else ""
        delta_str = f"{sign}{diff_pct:.1f}% ({sign}{diff_abs:.1f} kt)" if abs(diff_abs) >= 0.1 else "Baseline"

        return ui.div(
            {"class": "kpi-card"},
            ui.div("Annual CO₂ Emissions", class_="kpi-title"),
            ui.div(f"{scen_emi:.0f} kt", class_="kpi-value"),
            ui.div(f"{delta_str} vs baseline", class_=f"kpi-delta {delta_cls}"),
        )

    @render.ui
    def kpi_import_share():
        res = current_results()
        base_imp = BASELINE_RESULTS.import_share_pct
        scen_imp = res.import_share_pct
        diff = scen_imp - base_imp

        delta_cls = "good" if diff <= 0 else "bad"
        sign = "+" if diff > 0 else ""
        delta_str = f"{sign}{diff:.1f} pp" if abs(diff) >= 0.05 else "Baseline"

        return ui.div(
            {"class": "kpi-card"},
            ui.div("Import Dependency", class_="kpi-title"),
            ui.div(f"{scen_imp:.1f}%", class_="kpi-value"),
            ui.div(f"{delta_str} vs baseline", class_=f"kpi-delta {delta_cls}"),
        )

    @render.ui
    def kpi_renewables():
        res = current_results()
        base_ren = BASELINE_RESULTS.renewable_share_pct
        scen_ren = res.renewable_share_pct
        diff = scen_ren - base_ren

        delta_cls = "good" if diff >= 0 else "bad"
        sign = "+" if diff > 0 else ""
        delta_str = f"{sign}{diff:.1f} pp" if abs(diff) >= 0.05 else "Baseline"

        return ui.div(
            {"class": "kpi-card"},
            ui.div("Domestic Renewable Share", class_="kpi-title"),
            ui.div(f"{scen_ren:.1f}%", class_="kpi-value"),
            ui.div(f"{delta_str} vs baseline", class_=f"kpi-delta {delta_cls}"),
        )

    # --- Plotly Visualisations ---
    @render.ui
    def plot_generation_mix():
        res = current_results()

        # Build comparison Polars dataframe
        df_base = BASELINE_RESULTS.generation_mix.filter(
            pl.col("carrier").is_in(["solar", "wind", "gas", "import", "battery"])
        ).filter(pl.col("technology") != "Battery Charge")

        df_scen = res.generation_mix.filter(
            pl.col("carrier").is_in(["solar", "wind", "gas", "import", "battery"])
        ).filter(pl.col("technology") != "Battery Charge")

        fig = go.Figure()

        tech_labels = ["Solar PV", "Onshore Wind", "Battery Discharge", "Gas Generation", "Electricity Imports"]
        color_map = {
            "Solar PV": CARRIER_COLORS["solar"],
            "Onshore Wind": CARRIER_COLORS["wind"],
            "Battery Discharge": CARRIER_COLORS["battery"],
            "Gas Generation": CARRIER_COLORS["gas"],
            "Electricity Imports": CARRIER_COLORS["import"],
        }

        for tech in tech_labels:
            val_base = df_base.filter(pl.col("technology") == tech)["annual_generation_gwh"].to_list()
            val_scen = df_scen.filter(pl.col("technology") == tech)["annual_generation_gwh"].to_list()
            b_val = val_base[0] if val_base else 0.0
            s_val = val_scen[0] if val_scen else 0.0

            fig.add_trace(
                go.Bar(
                    name=tech,
                    x=["Baseline", "Scenario"],
                    y=[b_val, s_val],
                    marker_color=color_map[tech],
                    hovertemplate="%{y:.1f} GWh<extra></extra>",
                )
            )

        fig.update_layout(
            barmode="stack",
            height=340,
            margin=dict(l=40, r=20, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Annual Generation (GWh)", gridcolor="#f1f5f9"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    @render.ui
    def plot_capacities():
        res = current_results()

        df_base = BASELINE_RESULTS.capacities.filter(pl.col("unit") == "MW")
        df_scen = res.capacities.filter(pl.col("unit") == "MW")

        techs = df_base["technology"].to_list()
        base_caps = df_base["capacity"].to_list()
        scen_caps = df_scen["capacity"].to_list()

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Baseline",
                x=techs,
                y=base_caps,
                marker_color="#94a3b8",
                hovertemplate="%{y:.1f} MW<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Scenario",
                x=techs,
                y=scen_caps,
                marker_color="#0284c7",
                hovertemplate="%{y:.1f} MW<extra></extra>",
            )
        )

        fig.update_layout(
            barmode="group",
            height=340,
            margin=dict(l=40, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Installed Capacity (MW)", gridcolor="#f1f5f9"),
            xaxis=dict(tickangle=-15),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    @render.ui
    def plot_cost_breakdown():
        res = current_results()
        df = res.cost_breakdown.filter(pl.col("technology") != "Total System")

        techs = df["technology"].to_list()
        capex_m = [v / 1e6 for v in df["capex_eur_per_year"].to_list()]
        opex_m = [v / 1e6 for v in df["opex_eur_per_year"].to_list()]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Annualised CAPEX (€M)",
                x=techs,
                y=capex_m,
                marker_color="#3b82f6",
                hovertemplate="€%{y:.2f} M/yr<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Annual OPEX & Fuel (€M)",
                x=techs,
                y=opex_m,
                marker_color="#f97316",
                hovertemplate="€%{y:.2f} M/yr<extra></extra>",
            )
        )

        fig.update_layout(
            barmode="stack",
            height=280,
            margin=dict(l=40, r=20, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Annual Cost (€M / year)", gridcolor="#f1f5f9"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    @render.ui
    def plot_dispatch():
        res = current_results()
        df = res.hourly_dispatch

        snapshots = df["snapshot"].to_list()
        demand = df["demand_mw"].to_list()
        solar = df["solar_mw"].to_list()
        wind = df["wind_mw"].to_list()
        gas = df["gas_mw"].to_list()
        imp = df["import_mw"].to_list()
        bat_dis = df["battery_discharge_mw"].to_list()
        bat_chg = [-v for v in df["battery_charge_mw"].to_list()]  # Display charging as negative

        # Custom tick labels at start of each day (every 24 snapshots)
        day_ticks = [i * 24 for i in range(7)]
        day_labels = ["Mon 00:00", "Tue 00:00", "Wed 00:00", "Thu 00:00", "Fri 00:00", "Sat 00:00", "Sun 00:00"]

        fig = go.Figure()

        # Stacked positive generation
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=imp,
                name="Electricity Imports",
                stackgroup="supply",
                mode="lines",
                line=dict(width=0.5, color=CARRIER_COLORS["import"]),
                fillcolor=CARRIER_COLORS["import"],
                hovertemplate="Imports: %{y:.1f} MW<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=gas,
                name="Gas Generation",
                stackgroup="supply",
                mode="lines",
                line=dict(width=0.5, color=CARRIER_COLORS["gas"]),
                fillcolor=CARRIER_COLORS["gas"],
                hovertemplate="Gas: %{y:.1f} MW<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=wind,
                name="Onshore Wind",
                stackgroup="supply",
                mode="lines",
                line=dict(width=0.5, color=CARRIER_COLORS["wind"]),
                fillcolor=CARRIER_COLORS["wind"],
                hovertemplate="Wind: %{y:.1f} MW<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=solar,
                name="Solar PV",
                stackgroup="supply",
                mode="lines",
                line=dict(width=0.5, color=CARRIER_COLORS["solar"]),
                fillcolor=CARRIER_COLORS["solar"],
                hovertemplate="Solar: %{y:.1f} MW<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=bat_dis,
                name="Battery Discharge",
                stackgroup="supply",
                mode="lines",
                line=dict(width=0.5, color=CARRIER_COLORS["battery"]),
                fillcolor=CARRIER_COLORS["battery"],
                hovertemplate="Battery Discharge: %{y:.1f} MW<extra></extra>",
            )
        )

        # Battery Charging (negative area)
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=bat_chg,
                name="Battery Charging",
                mode="lines",
                line=dict(width=0.5, color="#9333ea"),
                fill="tozeroy",
                fillcolor="rgba(147, 51, 234, 0.35)",
                hovertemplate="Battery Charge: %{y:.1f} MW<extra></extra>",
            )
        )

        # Demand line
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=demand,
                name="Demand",
                mode="lines",
                line=dict(color="#0f172a", width=2.5, dash="solid"),
                hovertemplate="Demand: %{y:.1f} MW<extra></extra>",
            )
        )

        fig.update_layout(
            height=400,
            margin=dict(l=50, r=20, t=10, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                title="Representative Week Hour",
                tickmode="array",
                tickvals=day_ticks,
                ticktext=day_labels,
                gridcolor="#f1f5f9",
            ),
            yaxis=dict(title="Power (MW)", gridcolor="#f1f5f9"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            hovermode="x unified",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    @render.ui
    def plot_battery_soc():
        res = current_results()
        df = res.hourly_dispatch
        snapshots = df["snapshot"].to_list()
        soc = df["battery_soc_mwh"].to_list()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=snapshots,
                y=soc,
                name="Stored Energy",
                mode="lines",
                line=dict(color=CARRIER_COLORS["battery"], width=2),
                fill="tozeroy",
                fillcolor="rgba(142, 68, 173, 0.2)",
                hovertemplate="%{y:.1f} MWh<extra></extra>",
            )
        )
        fig.update_layout(
            height=240,
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(title="Hour of Week", gridcolor="#f1f5f9"),
            yaxis=dict(title="State of Charge (MWh)", gridcolor="#f1f5f9"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    @render.ui
    def plot_daily_profile():
        res = current_results()
        # Group by hour of day using Polars
        df = res.hourly_dispatch
        hourly_summary = (
            df.group_by("hour")
            .agg(
                pl.col("demand_mw").mean().alias("avg_demand"),
                pl.col("solar_mw").mean().alias("avg_solar"),
                pl.col("wind_mw").mean().alias("avg_wind"),
                pl.col("gas_mw").mean().alias("avg_gas"),
                pl.col("import_mw").mean().alias("avg_import"),
            )
            .sort("hour")
        )

        hours = hourly_summary["hour"].to_list()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=hourly_summary["avg_solar"].to_list(), name="Solar", line=dict(color=CARRIER_COLORS["solar"], width=2)))
        fig.add_trace(go.Scatter(x=hours, y=hourly_summary["avg_wind"].to_list(), name="Wind", line=dict(color=CARRIER_COLORS["wind"], width=2)))
        fig.add_trace(go.Scatter(x=hours, y=hourly_summary["avg_gas"].to_list(), name="Gas", line=dict(color=CARRIER_COLORS["gas"], width=2)))
        fig.add_trace(go.Scatter(x=hours, y=hourly_summary["avg_import"].to_list(), name="Import", line=dict(color=CARRIER_COLORS["import"], width=2)))
        fig.add_trace(go.Scatter(x=hours, y=hourly_summary["avg_demand"].to_list(), name="Demand", line=dict(color="#0f172a", width=2, dash="dash")))

        fig.update_layout(
            height=240,
            margin=dict(l=40, r=20, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="Hour of Day (0–23)", gridcolor="#f1f5f9"),
            yaxis=dict(title="Avg Power (MW)", gridcolor="#f1f5f9"),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        return ui.HTML(fig.to_html(include_plotlyjs=False, full_html=False))

    # --- Data Tables (Polars to dicts/list format for Shiny render.table) ---
    @render.table
    def table_capacities():
        res = current_results()
        df = res.capacities
        # Format numbers cleanly with Polars
        formatted = df.select(
            pl.col("technology").alias("Technology"),
            pl.col("capacity").round(1).alias("Installed Capacity"),
            pl.col("unit").alias("Unit"),
        )
        return formatted.to_dicts()

    @render.table
    def table_generation_mix():
        res = current_results()
        df = res.generation_mix
        formatted = df.select(
            pl.col("technology").alias("Technology"),
            pl.col("annual_generation_gwh").round(1).alias("Annual Generation (GWh)"),
            pl.col("share_of_supply_pct").round(1).alias("Share of Total Supply (%)"),
        )
        return formatted.to_dicts()

    @render.table
    def table_costs():
        res = current_results()
        df = res.cost_breakdown
        formatted = df.select(
            pl.col("technology").alias("Component"),
            (pl.col("capex_eur_per_year") / 1e6).round(2).alias("CAPEX (€M/year)"),
            (pl.col("opex_eur_per_year") / 1e6).round(2).alias("OPEX (€M/year)"),
            (pl.col("total_eur_per_year") / 1e6).round(2).alias("Total (€M/year)"),
        )
        return formatted.to_dicts()


app = App(app_ui, server)
