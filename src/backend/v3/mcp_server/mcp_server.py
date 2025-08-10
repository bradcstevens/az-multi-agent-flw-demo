"""
MACAE MCP Server - Unified server supporting both HTTP API and MCP protocol.
"""

import sys
import argparse
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.server.auth import BearerAuthProvider

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from typing import Optional

from core.factory import MCPToolFactory
from services import HRService, TechSupportService, GeneralService
from config.settings import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="MACAE MCP Server",
    description="Multi-Agent Custom Automation Engine - Model Context Protocol Server",
    version="1.0.0",
    docs_url="/docs" if config.debug else None,
    redoc_url="/redoc" if config.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global factory instance
factory = MCPToolFactory()

# Initialize services
factory.register_service(HRService())
factory.register_service(TechSupportService())
factory.register_service(GeneralService())


def create_fastmcp_server():
    """Create and configure FastMCP server."""
    try:

        # Create authentication provider if enabled
        auth = None
        if config.enable_auth:
            auth_config = {
                "jwks_uri": config.jwks_uri,
                "issuer": config.issuer,
                "audience": config.audience,
            }
            if all(auth_config.values()):
                auth = BearerAuthProvider(
                    jwks_uri=auth_config["jwks_uri"],
                    issuer=auth_config["issuer"],
                    algorithm="RS256",
                    audience=auth_config["audience"],
                )

        # Create MCP server
        mcp_server = factory.create_mcp_server(name=config.server_name, auth=auth)

        logger.info("✅ FastMCP server created successfully")
        return mcp_server

    except ImportError:
        logger.warning("⚠️  FastMCP not available. Install with: pip install fastmcp")
        return None


# Create FastMCP server instance for fastmcp run command
mcp = create_fastmcp_server()


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Verify authentication token if auth is enabled."""
    if not config.enable_auth:
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Here you would verify the JWT token
    # For now, we'll just check if a token is present
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    return token


@app.on_event("startup")
async def startup_event():
    """Log server info on startup."""
    global factory

    # Log server info
    summary = factory.get_tool_summary()
    logger.info(f"🚀 {config.server_name} initialized")
    logger.info(f"📊 Total services: {summary['total_services']}")
    logger.info(f"🔧 Total tools: {summary['total_tools']}")
    logger.info(f"🔐 Authentication: {'Enabled' if config.enable_auth else 'Disabled'}")

    for domain, info in summary["services"].items():
        logger.info(
            f"   📁 {domain}: {info['tool_count']} tools ({info['class_name']})"
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "MACAE MCP Server", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}


@app.get("/tools")
async def get_tools(token: Optional[str] = Depends(verify_token)):
    """Get available tools summary."""
    return factory.get_tool_summary()


@app.get("/tools/{domain}")
async def get_tools_by_domain(
    domain: str, token: Optional[str] = Depends(verify_token)
):
    """Get tools for a specific domain."""
    try:
        from core.factory import Domain

        domain_enum = Domain(domain.lower())
        service = factory.get_services_by_domain(domain_enum)

        if not service:
            raise HTTPException(status_code=404, detail=f"Domain {domain} not found")

        return {
            "domain": domain,
            "tool_count": service.tool_count,
            "service_class": service.__class__.__name__,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")


def run_http_server():
    """Run the HTTP API server."""
    logger.info(f"🌐 Starting HTTP API server on {config.host}:9000")
    uvicorn.run(
        "mcp_server:app",
        host=config.host,
        port=9000,
        reload=config.debug,
        log_level="info" if config.debug else "warning",
    )


def run_mcp_server():
    """Run the FastMCP protocol server."""
    global mcp
    if mcp:
        logger.info(f"🤖 Starting FastMCP server on {config.host}:9000")
        mcp.run()
    else:
        logger.error("❌ Cannot start FastMCP server - fastmcp not available")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="MACAE MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "mcp"],
        default="http",
        help="Server mode: 'http' for HTTP API, 'mcp' for FastMCP protocol (default: http)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication")

    args = parser.parse_args()

    # Override config with command line arguments
    if args.debug:
        import os

        os.environ["MCP_DEBUG"] = "true"
        config.debug = True

    if args.no_auth:
        import os

        os.environ["MCP_ENABLE_AUTH"] = "false"
        config.enable_auth = False

    # Print startup info
    print(f"🚀 Starting MACAE MCP Server")
    print(f"📋 Mode: {args.mode.upper()}")
    print(f"🔧 Debug: {config.debug}")
    print(f"🔐 Auth: {'Enabled' if config.enable_auth else 'Disabled'}")
    print(f"🌐 Port: 9000")
    print("-" * 50)

    # Run appropriate server
    if args.mode == "http":
        run_http_server()
    else:
        run_mcp_server()


if __name__ == "__main__":
    main()
