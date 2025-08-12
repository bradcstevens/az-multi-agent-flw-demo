# Team Configuration Upload Validation

This document describes the validation system for team configuration JSON uploads in the Multi-Agent Custom Automation Engine.

## Validation Pipeline

When a team configuration JSON file is uploaded, it goes through the following validation steps:

### 1. JSON Format Validation
- Validates that the file contains valid JSON
- Checks for proper syntax and structure

### 2. RAI (Responsible AI) Content Validation
- Validates content safety and appropriateness
- Checks agent `system_message`, `name`, and `description` fields
- Checks starting task `name` and `prompt` fields
- Rejects configurations with harmful, inappropriate, or unsafe content

### 3. Model Deployment Validation
- Validates that required AI models are deployed in Azure AI Foundry
- Extracts model references from agent configurations
- Checks against available model deployments
- Provides detailed error messages for missing models

### 4. RAG Search Index Validation (Conditional)
- **Only runs when the team configuration contains RAG agents**
- Validates that referenced search indexes exist in Azure AI Search
- Checks agents with `type: "RAG"` or non-empty `index_name` fields
- Provides specific error messages for missing or inaccessible indexes

### 5. Schema Validation
- Validates required fields based on the team configuration schema
- Ensures proper data types and structure
- Generates timestamps and IDs automatically

## Team Configuration Schema

```json
{
    "name": "string (required)",
    "description": "string (optional)",
    "status": "string (required)",
    "agents": [
        {
            "input_key": "string (required)",
            "type": "string (required)", // "MagenticOne", "RAG", "Custom"
            "name": "string (required)",
            "system_message": "string (optional)",
            "description": "string (optional)",
            "icon": "string (required)",
            "index_name": "string (optional)", // Required for RAG agents
            "model_name": "string (optional)"
        }
    ],
    "starting_tasks": [
        {
            "id": "string (required)",
            "name": "string (required)",
            "prompt": "string (required)",
            "created": "string (required)",
            "creator": "string (required)",
            "logo": "string (required)"
        }
    ]
}
```

## RAG Agent Detection

The system identifies RAG agents by:
1. **Agent type**: `"type": "RAG"`
2. **Index name**: Non-empty `index_name` field

If RAG agents are detected, the system validates that:
- Azure Search endpoint is configured (`AZURE_SEARCH_ENDPOINT`)
- All referenced search indexes exist and are accessible
- Proper authentication is available

## Error Messages

### RAI Validation Error
```
❌ Content Safety Check Failed

Your team configuration contains content that doesn't meet our safety guidelines. Please review and modify:

• Agent instructions and descriptions
• Task prompts and content
• Team descriptions

Ensure all content is appropriate, helpful, and follows ethical AI principles.
```

### Model Validation Error
```
The following required models are not deployed in your Azure AI project: gpt-4o, text-embedding-ada-002. 
Please deploy these models in Azure AI Foundry before uploading this team configuration.
```

### RAG Search Index Error
```
🔍 RAG Search Configuration Error

Your team configuration includes RAG/search agents but has search index issues:

• Verify search index names are correct
• Ensure indexes exist in Azure AI Search
• Check access permissions to search service
• Confirm RAG agent configurations

RAG agents require properly configured search indexes to function correctly.
```

## Test Files

The following test files are provided for validation testing:

### `test_team_no_rag.json`
- Basic team configuration without RAG functionality
- Should pass all validation steps
- Uses only `MagenticOne` and `Custom` agent types

### `test_team_with_rag.json`
- Team configuration with RAG agents
- Includes agents with `type: "RAG"` and `index_name` fields
- Will trigger search index validation
- Should fail if referenced indexes don't exist

### `test_team_rai_validation.json`
- Team configuration with inappropriate content
- Designed to test RAI validation
- Should fail RAI validation with helpful error message

## Environment Variables

Required environment variables for validation:

```bash
# For RAI validation
AZURE_OPENAI_ENDPOINT=your_openai_endpoint
AZURE_OPENAI_API_KEY=your_openai_key

# For model validation
AZURE_AI_PROJECT_NAME=your_project_name
AZURE_AI_HUB_NAME=your_hub_name
AZURE_SUBSCRIPTION_ID=your_subscription_id
AZURE_RESOURCE_GROUP_NAME=your_resource_group

# For RAG search validation (optional, only needed if using RAG agents)
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_search_key
```

## API Endpoints

### Upload Team Configuration
- **POST** `/upload_team_config`
- Accepts multipart/form-data with JSON file
- Returns success or detailed validation errors

### Debug Endpoints
- **GET** `/api/model_deployments` - List available model deployments
- **GET** `/api/search_indexes` - List available search indexes (if configured)

## Performance Considerations

- **RAG validation is conditional** - only runs when RAG agents are present
- **Validation is parallel** - multiple checks run simultaneously when possible
- **Early termination** - validation stops at first failure to provide quick feedback
- **Caching** - Model and search index information is cached for performance
