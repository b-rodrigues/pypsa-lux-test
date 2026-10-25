"""
Execution and solver status handling for the PyPSA optimization.
"""

from dataclasses import dataclass
from typing import Optional
import logging
import pypsa

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of an optimization run with explicit status reporting."""

    success: bool
    status: str
    termination_condition: str
    objective: Optional[float] = None
    error_message: Optional[str] = None
    network: Optional[pypsa.Network] = None


def run_model(
    network: pypsa.Network,
    solver_name: str = "highs",
) -> RunResult:
    """
    Run least-cost system optimization on the PyPSA network using HiGHS solver.

    Checks solver status and ensures that failed/infeasible runs are clearly reported.
    """
    try:
        status, termination_condition = network.optimize(
            solver_name=solver_name,
            solver_options={"log_to_console": False},
            include_objective_constant=False,
        )

        is_optimal = (
            status == "ok"
            and termination_condition in ["optimal", "locallyOptimal"]
        )

        if is_optimal:
            return RunResult(
                success=True,
                status=str(status),
                termination_condition=str(termination_condition),
                objective=float(network.objective),
                network=network,
            )
        else:
            return RunResult(
                success=False,
                status=str(status),
                termination_condition=str(termination_condition),
                objective=None,
                error_message=(
                    f"Solver finished with status '{status}' and condition '{termination_condition}'. "
                    "The problem may be infeasible or unconstrained."
                ),
                network=network,
            )

    except Exception as exc:
        logger.exception("Optimization run encountered an error")
        return RunResult(
            success=False,
            status="error",
            termination_condition="exception",
            objective=None,
            error_message=str(exc),
            network=network,
        )
