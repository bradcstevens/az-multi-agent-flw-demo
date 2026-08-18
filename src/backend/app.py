# app.py
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from common.config.app_config import config

# Configure logging levels FIRST, before any logging calls
logging.basicConfig(level=getattr(logging, config.AZURE_BASIC_LOGGING_LEVEL.upper(), logging.INFO))

from api.router import app_router
from azure.monitor.opentelemetry import configure_azure_monitor
from chat.reconcile import Reconciliation, reconcile_turns
from common.config.app_config import config
from common.database.database_factory import DatabaseFactory
from common.models.messages import UserLanguage
from config.agent_registry import agent_registry
# FastAPI imports
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Local imports
from middleware.health_check import HealthCheckMiddleware
# TEMPORARY — upstream PR #5690 (agent-framework 1.4.0) fixes the fc_ duplicate
# variant but NOT the orphaned function_call_output variant that also triggers
# "Progress ledger creation failed" in multi-agent Magentic workflows.
from patches import magentic_duplicate_fc_id

magentic_duplicate_fc_id.apply()

# How long the **Startup reconciliation** may hold the process short of ready.
# Bounded because a store that hangs would otherwise hold this process until the
# platform restarted it, and then hold the next one — a restart loop caused by
# the one operation that is explicitly allowed to fail.
RECONCILIATION_TIMEOUT_SECONDS = 30

# Azure monitoring


async def settle_inherited_turns() -> Optional[Reconciliation]:
    """**Startup reconciliation** — settle the turns this process inherited.

    #159, ADR-047. A turn runs inside an ``asyncio.Task`` held in memory by the
    process serving it, so a **Plan record** a *starting* process finds at an
    unsettled status describes a turn that no longer exists anywhere. Settling it
    reports what happened; it does not infer it. The backlog ADR-031 named —
    rows no exposed route can clear — therefore clears itself on the next deploy.

    Here rather than in a route because *starting* is the whole of the argument.
    The rule reaches only what this process inherited, and it is safe only while
    one process is all there is: ``infra/bicep/main.bicep`` pins every Container
    App to one replica and the ``single-replica`` preflight check fails the moment
    that stops being true. See ADR-047 before widening it.

    **Awaited before the application serves, and bounded.** It must finish first —
    a pass still running while requests arrive could settle a turn that started
    after it read, which is the one direction of error ADR-043 exists to prevent.
    But *blocking* and *never finishing* are different things: a store that hangs
    would hold the process short of ready until the platform restarted it, and
    then hold the next one, so the wait is bounded and a pass that overruns is
    abandoned exactly like one that raised.

    **A reconciliation that could not run does not stop the application
    starting.** A store that cannot answer is a demonstration that boots without
    its backlog cleared, which is the state it is in today; refusing to serve
    would turn a stale row into an outage. It is logged as *did not run* rather
    than as an empty backlog, because those are different facts and only one of
    them means the rows are gone.
    """
    logger = logging.getLogger(__name__)

    try:
        reconciled = await asyncio.wait_for(
            _reconcile_inherited_turns(), timeout=RECONCILIATION_TIMEOUT_SECONDS
        )
    except Exception:
        logger.error(
            "Startup reconciliation did not run to completion: chats left "
            "claiming to run by an earlier process may still be undeletable",
            exc_info=True,
        )
        return None

    logger.info("Startup reconciliation: %s", reconciled.summary)
    return reconciled


async def _reconcile_inherited_turns() -> Reconciliation:
    """The pass itself: read every Plan's state, settle the ones nobody is running."""
    store = await DatabaseFactory.get_database()
    return await reconcile_turns(
        await store.plan_states(), DatabaseFactory.get_database
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI application lifecycle - startup and shutdown."""
    logger = logging.getLogger(__name__)

    # Startup
    logger.info("Starting MACAE application...")
    await settle_inherited_turns()
    yield

    # Shutdown
    logger.info("Shutting down MACAE application...")
    try:
        # Clean up all agents from Azure AI Foundry when container stops
        await agent_registry.cleanup_all_agents()
        logger.info("Agent cleanup completed successfully")

    except ImportError as ie:
        logger.error(f"Could not import agent_registry: {ie}")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}")

    logger.info("MACAE application shutdown complete")


# Check if the Application Insights Instrumentation Key is set in the environment variables
connection_string = config.APPLICATIONINSIGHTS_CONNECTION_STRING
if connection_string:
    # Configure Application Insights if the Instrumentation Key is found
    configure_azure_monitor(connection_string=connection_string)
    logging.info(
        "Application Insights configured with the provided Instrumentation Key"
    )
else:
    # Log a warning if the Instrumentation Key is not found
    logging.warning(
        "No Application Insights Instrumentation Key found. Skipping configuration"
    )

# Configure logging levels from environment variables
# logging.basicConfig(level=getattr(logging, config.AZURE_BASIC_LOGGING_LEVEL.upper(), logging.INFO))

# Configure Azure package logging levels
azure_level = getattr(logging, config.AZURE_PACKAGE_LOGGING_LEVEL.upper(), logging.WARNING)
# Parse comma-separated logging packages
if config.AZURE_LOGGING_PACKAGES:
    packages = [pkg.strip() for pkg in config.AZURE_LOGGING_PACKAGES.split(",") if pkg.strip()]
    for logger_name in packages:
        logging.getLogger(logger_name).setLevel(azure_level)

for _af_logger in ("agent_framework", "agent_framework.openai"):
    logging.getLogger(_af_logger).setLevel(azure_level)

logging.getLogger("opentelemetry.sdk").setLevel(logging.ERROR)

logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

# Suppress noisy Azure Cosmos DB HTTP request/response logging
logging.getLogger("azure.cosmos._cosmos_http_logging_policy").setLevel(logging.WARNING)

# Suppress noisy Azure Monitor exporter "Transmission succeeded" logs
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(logging.WARNING)

# Initialize the FastAPI app
app = FastAPI(lifespan=lifespan)

frontend_url = config.FRONTEND_SITE_NAME
# Configure Azure Monitor and instrument FastAPI for OpenTelemetry
# This enables automatic request tracing, dependency tracking, and proper operation_id
if config.APPLICATIONINSIGHTS_CONNECTION_STRING:
    # Configure Application Insights telemetry with live metrics
    configure_azure_monitor(
        connection_string=config.APPLICATIONINSIGHTS_CONNECTION_STRING,
        enable_live_metrics=True
    )

    # Instrument FastAPI app — exclude WebSocket URLs to reduce telemetry noise
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="socket,ws"
    )
    logging.info("Application Insights configured with live metrics and WebSocket filtering")
else:
    logging.warning(
        "No Application Insights connection string found. Telemetry disabled."
    )

# Add this near the top of your app.py, after initializing the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure health check
app.add_middleware(HealthCheckMiddleware, password="", checks={})
# new flat-structure endpoints
app.include_router(app_router)
logging.info("Added health check middleware")


@app.post("/api/user_browser_language")
async def user_browser_language_endpoint(user_language: UserLanguage, request: Request):
    """
    Receive the user's browser language.

    ---
    tags:
      - User
    parameters:
      - name: language
        in: query
        type: string
        required: true
        description: The user's browser language
    responses:
      200:
        description: Language received successfully
        schema:
          type: object
          properties:
            status:
              type: string
              description: Confirmation message
    """
    config.set_user_local_browser_language(user_language.language)

    # Log the received language for the user
    logging.info(f"Received browser language '{user_language}' for user ")

    return {"status": "Language received successfully"}


# Run the app
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv"],
        log_level="info",
        access_log=False,
    )
