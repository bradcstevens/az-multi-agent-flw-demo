# Scenario Upload and Agent Creation Feature

## Overview

The `/api/upload_scenarios` endpoint allows users to upload JSON files containing scenario definitions and automatically create agents in Azure AI Foundry. This feature includes comprehensive RAI (Responsible AI) validation to ensure all content meets safety guidelines.

## API Endpoint

### POST `/api/upload_scenarios`

Upload scenario data and create agents in Azure AI Foundry.

**Headers:**
- `user_principal_id`: User ID extracted from authentication header (required)

**Parameters:**
- `file`: JSON file containing scenario data (required)

**Response Codes:**
- `200`: Scenarios processed and agents created successfully
- `400`: Invalid request, file format, or RAI validation failure
- `401`: Missing or invalid user information
- `500`: Internal server error

## JSON Structure

The uploaded JSON file must follow this structure:

```json
{
  "scenarios": [
    {
      "name": "Scenario Name",
      "description": "Scenario description",
      "agents": [
        {
          "name": "Agent Name",
          "description": "Agent description",
          "instructions": "Detailed agent instructions",
          "deployment_name": "model-deployment-name",
          "type": "agent_type",
          "tools": [
            {
              "type": "function",
              "function": {
                "name": "tool_name",
                "description": "Tool description"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Required Fields

**Scenario Level:**
- `name`: Scenario name
- `description`: Scenario description
- `agents`: Array of agent definitions

**Agent Level:**
- `name`: Agent name (must be unique)
- `description`: Agent description
- `instructions`: Agent system instructions
- `deployment_name`: Model deployment name in Azure AI Foundry
- `type`: Agent type identifier

**Optional Fields:**
- `tools`: Array of tool definitions for the agent

## Validation Process

The endpoint performs the following validation steps:

### 1. File Validation
- Verifies file is provided
- Checks file has `.json` extension
- Validates JSON syntax

### 2. Structure Validation
- Ensures JSON contains valid object
- Validates presence of `scenarios` array
- Checks that at least one scenario is provided

### 3. RAI (Responsible AI) Validation
- Validates all description and instruction fields
- Rejects content containing:
  - Harmful or dangerous instructions
  - Biased or discriminatory content
  - Inappropriate or offensive material
  - Content violating ethical AI principles

### 4. Agent Creation
- Extracts agent configurations from scenarios
- Creates agents in Azure AI Foundry using the AI Project client
- Tracks success and failure counts

## Response Format

### Success Response
```json
{
  "status": "success",
  "message": "Successfully created all 5 agents in Azure AI Foundry",
  "results": {
    "total_agents": 5,
    "created_count": 5,
    "failed_count": 0,
    "created_agents": [
      {
        "name": "Agent Name",
        "agent_id": "agent-id-in-foundry",
        "scenario": "Scenario Name",
        "deployment_name": "gpt-4o"
      }
    ],
    "failed_agents": []
  }
}
```

### Partial Success Response
```json
{
  "status": "partial_success",
  "message": "Created 3 agents successfully, but 2 failed",
  "results": {
    "total_agents": 5,
    "created_count": 3,
    "failed_count": 2,
    "created_agents": [...],
    "failed_agents": [
      {
        "name": "Failed Agent",
        "scenario": "Scenario Name",
        "error": "Error message"
      }
    ]
  }
}
```

### Error Response
```json
{
  "detail": "RAI validation failed: Content contains inappropriate material"
}
```

## Implementation Details

### Services

**FoundryAgentService** (`src/backend/services/foundry_agent_service.py`)
- Handles scenario processing and agent creation
- Integrates with Azure AI Foundry API
- Manages RAI validation workflow

### Key Methods

1. **`validate_scenario_descriptions()`**
   - Uses existing RAI validation infrastructure
   - Validates all text content in scenarios

2. **`extract_scenarios_and_agents()`**
   - Parses JSON structure
   - Extracts agent configurations
   - Validates required fields

3. **`create_foundry_agent()`**
   - Creates individual agents in Azure AI Foundry
   - Handles API errors gracefully

4. **`create_agents_from_scenarios()`**
   - Orchestrates the complete workflow
   - Returns comprehensive results

### Error Handling

- **RAI Failures**: Complete rejection of file processing
- **Individual Agent Failures**: Partial success with detailed error reporting
- **API Errors**: Graceful handling with retry logic where appropriate
- **Validation Errors**: Clear error messages for structure issues

## Usage Examples

### Example 1: Customer Support Scenario
```json
{
  "scenarios": [
    {
      "name": "Customer Support Automation",
      "description": "Multi-agent customer support system",
      "agents": [
        {
          "name": "Triage Agent",
          "description": "Routes customer inquiries to appropriate specialists",
          "instructions": "Categorize and route customer inquiries professionally and efficiently",
          "deployment_name": "gpt-4o",
          "type": "support_triage"
        }
      ]
    }
  ]
}
```

### Example 2: E-commerce Processing
```json
{
  "scenarios": [
    {
      "name": "Order Processing",
      "description": "Automated order validation and fulfillment",
      "agents": [
        {
          "name": "Order Validator",
          "description": "Validates incoming orders",
          "instructions": "Review orders for completeness and accuracy",
          "deployment_name": "gpt-35-turbo",
          "type": "order_validation",
          "tools": [
            {
              "type": "function",
              "function": {
                "name": "validate_payment",
                "description": "Validate payment information"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## Testing

Use the provided test files:
- `example_scenarios.json`: Valid scenario data for testing success path
- `test_scenarios_rai_fail.json`: Invalid content for testing RAI validation
- `test_scenario_processing.py`: Test script for local validation

## Security Considerations

1. **Authentication**: Requires valid user authentication
2. **RAI Validation**: Mandatory content safety checks
3. **Input Validation**: Comprehensive structure and format validation
4. **Error Handling**: No sensitive information exposed in error messages
5. **Audit Trail**: All operations are logged and tracked

## Future Enhancements

1. **Batch Processing**: Support for larger scenario uploads
2. **Template Library**: Pre-built scenario templates
3. **Agent Versioning**: Version management for created agents
4. **Advanced Tools**: Support for more complex tool definitions
5. **Integration Testing**: Automated testing of created agents
