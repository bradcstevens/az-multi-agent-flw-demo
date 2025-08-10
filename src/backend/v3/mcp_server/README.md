# MACAE MCP Server

A unified Model Context Protocol (MCP) server for the Multi-Agent Custom Automation Engine (MACAE) solution accelerator.

## Features

- **Unified Server**: Single `mcp_server.py` supporting both HTTP API and MCP protocol
  -# Get HR tools (with auth if enabled)
  curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:9000/tools/hr

````

## MCP Client Usage

For MCP clients, connect to the MCP server:

```python
from fastmcp import Client

client = Client("http://localhost:9000")

async with client:
    result = await client.call_tool("greet", {"name": "World"})
    print(result)
````

### Quick Test

**Test HTTP API mode:**

```bash
# Start the HTTP server
python mcp_server.py --mode http

# In another terminal, test the API
curl http://localhost:9000/tools | jq
curl -X POST http://localhost:9000/tools/list_employees | jq
```

**Test MCP Protocol mode:**

```bash
# Start the MCP server
python mcp_server.py --mode mcp

# Test with the included client
python client_example.py
```

**Test with FastMCP CLI (recommended for MCP clients):**

```bash
# Using fastmcp run command (streamable HTTP transport)
fastmcp run mcp_server.py -t streamable-http --port 9000 -l DEBUG

# Or use the helper script
python run_fastmcp.py

# Server will be available at: http://127.0.0.1:9000/mcp/
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're in the correct directory and dependencies are installed
2. **Authentication Errors**: Check your Azure AD configuration and tokens
3. **Port Conflicts**: Change the port in configuration if 9000 is already in use
4. **Missing fastmcp**: Install with `pip install fastmcp`**Factory Pattern**: Reusable MCP tools factory for easy service management

- **Domain-Based Organization**: Services organized by business domains (HR, Tech Support, etc.)
- **Authentication**: Optional Azure AD authentication support
- **Dual Protocol Support**: HTTP API (FastAPI) and MCP protocol in one server
- **Docker Support**: Containerized deployment with health checks
- **VS Code Integration**: Debug configurations and development settings
- **Comprehensive Testing**: Unit tests with pytest
- **Flexible Configuration**: Environment-based configuration management

## Architecture

```
src/backend/v3/mcp_server/
├── core/                   # Core factory and base classes
│   ├── __init__.py
│   └── factory.py         # MCPToolFactory and base classes
├── services/               # Domain-specific service implementations
│   ├── __init__.py
│   ├── hr_service.py      # Human Resources tools
│   ├── tech_support_service.py # IT/Tech Support tools
│   └── general_service.py # General purpose tools
├── utils/                  # Utility functions
│   ├── __init__.py
│   ├── date_utils.py      # Date formatting utilities
│   └── formatters.py      # Response formatting utilities
├── config/                 # Configuration management
│   ├── __init__.py
│   └── settings.py        # Settings and configuration
├── mcp_server.py          # Unified server (HTTP API + MCP protocol)
├── requirements.txt       # Python dependencies
├── uv.lock               # Lock file for dependencies
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Development container setup
└── .vscode/              # VS Code configurations
    ├── launch.json       # Debug configurations
    └── settings.json     # Editor settings
```

## Available Services

### HR Service (Domain: hr)

- **schedule_orientation_session**: Schedule orientation for new employees
- **assign_mentor**: Assign mentors to new employees
- **register_for_benefits**: Register employees for benefits
- **provide_employee_handbook**: Provide employee handbook
- **initiate_background_check**: Start background verification
- **request_id_card**: Request employee ID cards
- **set_up_payroll**: Configure payroll for employees

### Tech Support Service (Domain: tech_support)

- **send_welcome_email**: Send welcome emails to new employees
- **set_up_office_365_account**: Create Office 365 accounts
- **configure_laptop**: Configure laptops for employees
- **setup_vpn_access**: Configure VPN access
- **create_system_accounts**: Create system accounts

### General Service (Domain: general)

- **greet**: Simple greeting function
- **get_server_status**: Retrieve server status information

## Quick Start

### Development Setup

1. **Clone and Navigate**:

   ```bash
   cd src/backend/v3/mcp_server
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start the Server**:

   ````bash
   # HTTP API mode (default) - for REST clients
   python mcp_server.py

   # MCP protocol mode - for MCP clients
   python mcp_server.py --mode mcp

   # FastMCP CLI (recommended for MCP clients) - streamable HTTP transport
   fastmcp run mcp_server.py -t streamable-http --port 9000 -l DEBUG

   # Debug mode with authentication disabled
   python mcp_server.py --debug --no-auth
   ```### Server Modes
   ````

**The unified `mcp_server.py` supports two modes:**

**1. HTTP API Mode (default)**

- 🌐 FastAPI-based REST API
- 📚 Automatic Swagger/OpenAPI documentation
- 🔗 CORS support for web clients
- 🔧 HTTP endpoints for all MCP tools
- 💡 Perfect for: Web apps, curl, Postman, REST clients
- 🌐 **Port: 9000**

**2. MCP Protocol Mode**

- 🤖 Model Context Protocol compliant
- ⚡ Direct tool invocation protocol
- 🔌 MCP client compatibility
- 💡 Perfect for: AI agents, MCP-compatible clients
- 🌐 **Port: 9000**

### Docker Deployment

1. **Build and Run**:

   ```bash
   docker-compose up --build
   ```

2. **Access the API**:
   - Health check: http://localhost:9000/health
   - API docs: http://localhost:9000/docs (when debug=true)
   - Tools summary: http://localhost:9000/tools

### VS Code Development

1. **Open in VS Code**:

   ```bash
   code .
   ```

2. **Use Debug Configurations**:
   - `Debug MCP Server (MCP mode)`: Run the server in MCP protocol mode
   - `Debug HTTP Server (HTTP mode)`: Run the server in HTTP API mode
   - `Debug Tests`: Run the test suite

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Server Settings
MCP_HOST=0.0.0.0
MCP_PORT=9000
MCP_DEBUG=false
MCP_SERVER_NAME=MACAE MCP Server

# Authentication Settings
MCP_ENABLE_AUTH=true
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_JWKS_URI=https://login.microsoftonline.com/your-tenant-id/discovery/v2.0/keys
AZURE_ISSUER=https://sts.windows.net/your-tenant-id/
AZURE_AUDIENCE=api://your-client-id
```

### Authentication

When `MCP_ENABLE_AUTH=true`, the server expects Azure AD Bearer tokens. Configure your Azure App Registration with the appropriate settings.

For development, set `MCP_ENABLE_AUTH=false` to disable authentication.

## Adding New Services

1. **Create Service Class**:

   ```python
   from core.factory import MCPToolBase, Domain

   class MyService(MCPToolBase):
       def __init__(self):
           super().__init__(Domain.MY_DOMAIN)

       def register_tools(self, mcp):
           @mcp.tool(tags={self.domain.value})
           async def my_tool(param: str) -> str:
               # Tool implementation
               pass

       @property
       def tool_count(self) -> int:
           return 1  # Number of tools
   ```

2. **Register in Server**:

   ```python
   # In mcp_server.py (gets registered automatically from services/ directory)
   factory.register_service(MyService())
   ```

3. **Add Domain** (if new):
   ```python
   # In core/factory.py
   class Domain(Enum):
       # ... existing domains
       MY_DOMAIN = "my_domain"
   ```

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest src/tests/mcp_server/

# Run with coverage
pytest --cov=. src/tests/mcp_server/

# Run specific test file
pytest src/tests/mcp_server/test_hr_service.py -v
```

## API Endpoints (HTTP Server)

### Available Endpoints

- `GET /`: Server information
- `GET /health`: Health check
- `GET /tools`: Get all tools summary
- `GET /tools/{domain}`: Get tools for specific domain

### Example API Calls

```bash
# Health check
curl http://localhost:9000/health

# Get tools summary
curl http://localhost:9000/tools

# Get HR tools (with auth if enabled)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/tools/hr
```

## MCP Client Usage

For MCP clients, connect to the FastMCP server:

```python
from fastmcp import Client

client = Client("http://localhost:8000")

async with client:
    result = await client.call_tool("greet", {"name": "World"})
    print(result)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're in the correct directory and dependencies are installed
2. **Authentication Errors**: Check your Azure AD configuration and tokens
3. **Port Conflicts**: Change the port in configuration if 8000 is already in use
4. **Missing fastmcp**: Install with `pip install fastmcp`

### Debug Mode

Enable debug mode for detailed logging:

```env
MCP_DEBUG=true
```

### Logs

Check container logs:

```bash
docker-compose logs mcp-server
```

## Contributing

1. Follow the existing code structure and patterns
2. Add tests for new functionality
3. Update documentation for new features
4. Use the provided VS Code configurations for development

## License

This project is part of the MACAE Solution Accelerator and follows the same licensing terms.
