"""Unit tests for CosmosDB implementation."""

import datetime
import logging
import sys
import os
from unittest.mock import AsyncMock, Mock, call, patch
import pytest

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))

# Set required environment variables for testing
os.environ.setdefault('APPLICATIONINSIGHTS_CONNECTION_STRING', 'test_connection_string')
os.environ.setdefault('APP_ENV', 'dev')

# Only mock external problematic dependencies - do NOT mock internal common.* modules
sys.modules['azure'] = Mock()
sys.modules['azure.cosmos'] = Mock()
sys.modules['azure.cosmos.aio'] = Mock()
sys.modules['azure.cosmos.aio._database'] = Mock()
sys.modules['azure.core'] = Mock()
sys.modules['azure.core.exceptions'] = Mock()
sys.modules['azure.identity'] = Mock()
sys.modules['azure.identity.aio'] = Mock()
# Mock v4 modules — no longer needed (flat layout migration complete)

# Import the REAL modules using backend.* paths for proper coverage tracking
from backend.common.database.cosmosdb import CosmosDBClient
from backend.common.models.messages import (
    AgentMessage,
    AgentMessageData,
    BaseDataModel,
    CurrentTeamAgent,
    DataType,
    Plan,
    PlanStatus,
    Step,
    TeamConfiguration,
    UserCurrentTeam,
)
from chat.deletion import ChatDeletion, DeletionOutcome
from models.plan_models import MPlan


class TestCosmosDBClientInitialization:
    """Test CosmosDB client initialization and setup."""
    
    def test_initialization_with_all_parameters(self):
        """Test CosmosDB client initialization with all parameters."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        
        assert client.endpoint == "https://test.documents.azure.com:443/"
        assert client.credential == "test_credential"
        assert client.database_name == "test_db"
        assert client.container_name == "test_container"
        assert client.session_id == "test_session"
        assert client.user_id == "test_user"
        assert client._initialized is False
        assert client.client is None
        assert client.database is None
        assert client.container is None
    
    def test_initialization_with_minimal_parameters(self):
        """Test CosmosDB client initialization with minimal parameters."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container"
        )
        
        assert client.session_id == ""
        assert client.user_id == ""
        assert isinstance(client.logger, logging.Logger)
        
    def test_model_class_mapping(self):
        """Test that model class mapping is correctly defined."""
        mapping = CosmosDBClient.MODEL_CLASS_MAPPING
        
        assert mapping[DataType.plan] == Plan
        assert mapping[DataType.step] == Step
        assert mapping[DataType.agent_message] == AgentMessage
        assert mapping[DataType.team_config] == TeamConfiguration
        assert mapping[DataType.user_current_team] == UserCurrentTeam


class TestCosmosDBClientInitializationProcess:
    """Test CosmosDB client initialization process."""
    
    @pytest.fixture
    def client(self):
        """Create a CosmosDB client for testing."""
        return CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, client):
        """Test successful initialization."""
        mock_client = Mock()
        mock_database = Mock()
        mock_container = Mock()
        
        with patch('backend.common.database.cosmosdb.CosmosClient', return_value=mock_client):
            mock_client.get_database_client.return_value = mock_database
            client._get_container = AsyncMock(return_value=mock_container)
            
            await client.initialize()
            
            assert client.client == mock_client
            assert client.database == mock_database
            assert client.container == mock_container
            assert client._initialized is True
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, client):
        """Test initialization failure handling."""
        with patch('backend.common.database.cosmosdb.CosmosClient', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await client.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, client):
        """Test that initialization is skipped if already initialized."""
        client._initialized = True
        mock_client = AsyncMock()
        
        with patch('backend.common.database.cosmosdb.CosmosClient', return_value=mock_client) as mock_cosmos:
            await client.initialize()
            
            # Should not create new client if already initialized
            mock_cosmos.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ensure_initialized_calls_initialize(self, client):
        """Test that _ensure_initialized calls initialize when not initialized."""
        client.initialize = AsyncMock()
        
        await client._ensure_initialized()
        
        client.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_initialized_skips_when_initialized(self, client):
        """Test that _ensure_initialized skips initialization when already initialized."""
        client._initialized = True
        client.initialize = AsyncMock()
        
        await client._ensure_initialized()
        
        client.initialize.assert_not_called()


class TestCosmosDBContainerOperations:
    """Test CosmosDB container operations."""
    
    @pytest.fixture
    def client(self):
        """Create a CosmosDB client for testing."""
        return CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
    
    @pytest.mark.asyncio
    async def test_get_container_success(self, client):
        """Test successful container retrieval."""
        mock_database = Mock()
        mock_container = Mock()
        mock_database.get_container_client.return_value = mock_container
        
        result = await client._get_container(mock_database, "test_container")
        
        assert result == mock_container
        mock_database.get_container_client.assert_called_once_with("test_container")
    
    @pytest.mark.asyncio
    async def test_get_container_failure(self, client):
        """Test container retrieval failure."""
        mock_database = Mock()
        mock_database.get_container_client.side_effect = Exception("Container not found")
        
        # Mock the logger to avoid the error argument issue
        with patch.object(client, 'logger'):
            with pytest.raises(Exception, match="Container not found"):
                await client._get_container(mock_database, "test_container")
    
    @pytest.mark.asyncio
    async def test_close_connection(self, client):
        """Test closing CosmosDB connection."""
        mock_client = AsyncMock()
        client.client = mock_client
        
        await client.close()
        
        mock_client.close.assert_called_once()


class TestCosmosDBCRUDOperations:
    """Test CosmosDB CRUD operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_add_item_success(self, client):
        """Test successful item addition."""
        mock_item = Mock()
        mock_item.model_dump.return_value = {"id": "test_id", "data": "test_data"}
        
        await client.add_item(mock_item)
        
        client.container.create_item.assert_called_once_with(body={"id": "test_id", "data": "test_data"})
    
    @pytest.mark.asyncio
    async def test_add_item_with_datetime(self, client):
        """Test item addition with datetime serialization."""
        mock_item = Mock()
        test_datetime = datetime.datetime(2023, 1, 1, 12, 0, 0)
        mock_item.model_dump.return_value = {"id": "test_id", "timestamp": test_datetime}
        
        await client.add_item(mock_item)
        
        expected_body = {"id": "test_id", "timestamp": test_datetime.isoformat()}
        client.container.create_item.assert_called_once_with(body=expected_body)
    
    @pytest.mark.asyncio
    async def test_add_item_failure(self, client):
        """Test item addition failure."""
        mock_item = Mock()
        mock_item.model_dump.return_value = {"id": "test_id"}
        client.container.create_item.side_effect = Exception("Create failed")
        
        with pytest.raises(Exception, match="Create failed"):
            await client.add_item(mock_item)
    
    @pytest.mark.asyncio
    async def test_update_item_success(self, client):
        """Test successful item update."""
        mock_item = Mock()
        mock_item.model_dump.return_value = {"id": "test_id", "data": "updated_data"}
        
        await client.update_item(mock_item)
        
        client.container.upsert_item.assert_called_once_with(body={"id": "test_id", "data": "updated_data"})
    
    @pytest.mark.asyncio
    async def test_update_item_with_datetime(self, client):
        """Test item update with datetime serialization."""
        mock_item = Mock()
        test_datetime = datetime.datetime(2023, 1, 1, 12, 0, 0)
        mock_item.model_dump.return_value = {"id": "test_id", "timestamp": test_datetime}
        
        await client.update_item(mock_item)
        
        expected_body = {"id": "test_id", "timestamp": test_datetime.isoformat()}
        client.container.upsert_item.assert_called_once_with(body=expected_body)
    
    @pytest.mark.asyncio
    async def test_update_item_failure(self, client):
        """Test item update failure."""
        mock_item = Mock()
        mock_item.model_dump.return_value = {"id": "test_id"}
        client.container.upsert_item.side_effect = Exception("Update failed")
        
        with pytest.raises(Exception, match="Update failed"):
            await client.update_item(mock_item)
    
    @pytest.mark.asyncio
    async def test_get_item_by_id_success(self, client):
        """Test successful item retrieval by ID."""
        mock_data = {"id": "test_id", "data": "test_data"}
        client.container.read_item.return_value = mock_data
        
        mock_model_class = Mock()
        mock_instance = Mock()
        mock_model_class.model_validate.return_value = mock_instance
        
        result = await client.get_item_by_id("test_id", "partition_key", mock_model_class)
        
        assert result == mock_instance
        client.container.read_item.assert_called_once_with(item="test_id", partition_key="partition_key")
        mock_model_class.model_validate.assert_called_once_with(mock_data)
    
    @pytest.mark.asyncio
    async def test_get_item_by_id_not_found(self, client):
        """Test item retrieval when item not found."""
        client.container.read_item.side_effect = Exception("Item not found")
        
        mock_model_class = Mock()
        
        result = await client.get_item_by_id("test_id", "partition_key", mock_model_class)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_item_success(self, client):
        """Test successful item deletion."""
        await client.delete_item("test_id", "partition_key")
        
        client.container.delete_item.assert_called_once_with(item="test_id", partition_key="partition_key")
    
    @pytest.mark.asyncio
    async def test_delete_item_failure(self, client):
        """Test item deletion failure."""
        client.container.delete_item.side_effect = Exception("Delete failed")
        
        with pytest.raises(Exception, match="Delete failed"):
            await client.delete_item("test_id", "partition_key")


class TestCosmosDBQueryOperations:
    """Test CosmosDB query operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_query_items_success(self, client):
        """Test successful items query."""
        mock_data = [{"id": "1", "data": "test1"}, {"id": "2", "data": "test2"}]
        
        mock_model_class = Mock()
        mock_instances = [Mock(), Mock()]
        mock_model_class.model_validate.side_effect = mock_instances
        
        query = "SELECT * FROM c WHERE c.id = @id"
        parameters = [{"name": "@id", "value": "test"}]
        
        # Mock the container.query_items to return an async iterable
        async def async_gen():
            for item in mock_data:
                yield item
        
        client.container.query_items = Mock(return_value=async_gen())
        
        result = await client.query_items(query, parameters, mock_model_class)
        
        assert len(result) == 2
        assert result == mock_instances
    
    @pytest.mark.asyncio
    async def test_query_items_with_validation_error(self, client):
        """Test query with validation errors."""
        mock_data = [{"id": "1", "valid": True}, {"id": "2", "invalid": True}]
        
        mock_model_class = Mock()
        mock_instance = Mock()
        mock_model_class.model_validate.side_effect = [mock_instance, Exception("Validation failed")]
        
        query = "SELECT * FROM c"
        parameters = []
        
        # Mock the container.query_items to return an async iterable
        async def async_gen():
            for item in mock_data:
                yield item
        
        client.container.query_items = Mock(return_value=async_gen())
        
        result = await client.query_items(query, parameters, mock_model_class)
        
        # Should return only valid items
        assert len(result) == 1
        assert result == [mock_instance]
    
    @pytest.mark.asyncio
    async def test_query_items_failure(self, client):
        """Test query failure."""
        client.container.query_items.side_effect = Exception("Query failed")
        
        query = "SELECT * FROM c"
        parameters = []
        mock_model_class = Mock()
        
        result = await client.query_items(query, parameters, mock_model_class)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_all_items(self, client):
        """Test getting all items as dictionaries."""
        mock_data = [{"id": "1", "data": "test1"}, {"id": "2", "data": "test2"}]
        
        # Mock the container.query_items to return an async iterable
        async def async_gen():
            for item in mock_data:
                yield item
        
        client.container.query_items = Mock(return_value=async_gen())
        
        result = await client.get_all_items()
        
        assert result == mock_data


class TestCosmosDBPlanOperations:
    """Test CosmosDB plan-related operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_add_plan(self, client):
        """Test adding a plan."""
        mock_plan = Mock(spec=Plan)
        
        await client.add_plan(mock_plan)
        
        client.add_item.assert_called_once_with(mock_plan)
    
    @pytest.mark.asyncio
    async def test_update_plan(self, client):
        """Test updating a plan."""
        mock_plan = Mock(spec=Plan)
        
        await client.update_plan(mock_plan)
        
        client.update_item.assert_called_once_with(mock_plan)
    
    @pytest.mark.asyncio
    async def test_get_plan_by_plan_id_found(self, client):
        """Test getting a plan by plan_id when found."""
        mock_plan = Mock(spec=Plan)
        client.query_items.return_value = [mock_plan]
        
        result = await client.get_plan_by_plan_id("test_plan_id")
        
        assert result == mock_plan
        expected_query = "SELECT * FROM c WHERE c.id=@plan_id AND c.data_type=@data_type"
        expected_params = [
            {"name": "@plan_id", "value": "test_plan_id"},
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@user_id", "value": "test_user"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Plan)
    
    @pytest.mark.asyncio
    async def test_get_plan_by_plan_id_not_found(self, client):
        """Test getting a plan by plan_id when not found."""
        client.query_items.return_value = []
        
        result = await client.get_plan_by_plan_id("test_plan_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_plan(self, client):
        """Test get_plan method (alias for get_plan_by_plan_id)."""
        mock_plan = Mock(spec=Plan)
        client.query_items.return_value = [mock_plan]
        
        result = await client.get_plan("test_plan_id")
        
        assert result == mock_plan
    
    @pytest.mark.asyncio
    async def test_get_all_plans(self, client):
        """Test getting all plans for user."""
        mock_plans = [Mock(spec=Plan), Mock(spec=Plan)]
        client.query_items.return_value = mock_plans
        
        result = await client.get_all_plans()
        
        assert result == mock_plans
        expected_query = "SELECT * FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"
        expected_params = [
            {"name": "@user_id", "value": "test_user"},
            {"name": "@data_type", "value": DataType.plan},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Plan)
    
    @pytest.mark.asyncio
    async def test_get_all_plans_by_team_id(self, client):
        """Test getting all plans by team ID."""
        mock_plans = [Mock(spec=Plan), Mock(spec=Plan)]
        client.query_items.return_value = mock_plans
        
        result = await client.get_all_plans_by_team_id("test_team_id")
        
        assert result == mock_plans
        # Newest chat first. This became the chat list's read when #74 dropped
        # the status filter, and the filtered query it replaced carried this
        # ordering — losing it would leave the panel's row order to Cosmos.
        expected_query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type and c.user_id=@user_id ORDER BY c._ts DESC"
        expected_params = [
            {"name": "@user_id", "value": "test_user"},
            {"name": "@team_id", "value": "test_team_id"},
            {"name": "@data_type", "value": DataType.plan},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Plan)
    
    @pytest.mark.asyncio
    async def test_get_all_plans_by_team_id_status(self, client):
        """Test getting all plans by team ID and status."""
        mock_plans = [Mock(spec=Plan)]
        client.query_items.return_value = mock_plans
        
        result = await client.get_all_plans_by_team_id_status("user123", "team456", "active")
        
        assert result == mock_plans
        expected_query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type and c.user_id=@user_id and c.overall_status=@status ORDER BY c._ts DESC"
        expected_params = [
            {"name": "@user_id", "value": "user123"},
            {"name": "@team_id", "value": "team456"},
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@status", "value": "active"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Plan)


class TestCosmosDBStepOperations:
    """Test CosmosDB step-related operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_add_step(self, client):
        """Test adding a step."""
        mock_step = Mock(spec=Step)
        
        await client.add_step(mock_step)
        
        client.add_item.assert_called_once_with(mock_step)
    
    @pytest.mark.asyncio
    async def test_update_step(self, client):
        """Test updating a step."""
        mock_step = Mock(spec=Step)
        
        await client.update_step(mock_step)
        
        client.update_item.assert_called_once_with(mock_step)
    
    @pytest.mark.asyncio
    async def test_get_steps_by_plan(self, client):
        """Test getting steps by plan ID."""
        mock_steps = [Mock(spec=Step), Mock(spec=Step)]
        client.query_items.return_value = mock_steps
        
        result = await client.get_steps_by_plan("test_plan_id")
        
        assert result == mock_steps
        expected_query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type ORDER BY c.timestamp"
        expected_params = [
            {"name": "@plan_id", "value": "test_plan_id"},
            {"name": "@data_type", "value": DataType.step},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Step)
    
    @pytest.mark.asyncio
    async def test_get_step_found(self, client):
        """Test getting a step by ID and session ID when found."""
        mock_step = Mock(spec=Step)
        client.query_items.return_value = [mock_step]
        
        result = await client.get_step("test_step_id", "test_session_id")
        
        assert result == mock_step
        expected_query = "SELECT * FROM c WHERE c.id=@step_id AND c.session_id=@session_id AND c.data_type=@data_type"
        expected_params = [
            {"name": "@step_id", "value": "test_step_id"},
            {"name": "@session_id", "value": "test_session_id"},
            {"name": "@data_type", "value": DataType.step},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Step)
    
    @pytest.mark.asyncio
    async def test_get_step_not_found(self, client):
        """Test getting a step when not found."""
        client.query_items.return_value = []
        
        result = await client.get_step("test_step_id", "test_session_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_steps_for_plan_alias(self, client):
        """Test get_steps_for_plan method (alias for get_steps_by_plan)."""
        mock_steps = [Mock(spec=Step)]
        client.query_items.return_value = mock_steps
        
        result = await client.get_steps_for_plan("test_plan_id")
        
        assert result == mock_steps


class TestCosmosDBTeamOperations:
    """Test CosmosDB team-related operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        client.delete_item = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_add_team(self, client):
        """Test adding a team configuration."""
        mock_team = Mock(spec=TeamConfiguration)
        
        await client.add_team(mock_team)
        
        client.add_item.assert_called_once_with(mock_team)
    
    @pytest.mark.asyncio
    async def test_update_team(self, client):
        """Test updating a team configuration."""
        mock_team = Mock(spec=TeamConfiguration)
        
        await client.update_team(mock_team)
        
        client.update_item.assert_called_once_with(mock_team)
    
    @pytest.mark.asyncio
    async def test_get_team_found(self, client):
        """Test getting a team by team_id when found."""
        mock_team = Mock(spec=TeamConfiguration)
        client.query_items.return_value = [mock_team]
        
        result = await client.get_team("test_team_id")
        
        assert result == mock_team
        expected_query = (
            "SELECT * FROM c WHERE c.team_id=@team_id "
            "AND c.data_type=@data_type "
            "AND (c.user_id=@user_id OR c.is_default=true) "
            "ORDER BY c._ts DESC"
        )
        expected_params = [
            {"name": "@team_id", "value": "test_team_id"},
            {"name": "@data_type", "value": DataType.team_config},
            {"name": "@user_id", "value": "test_user"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, TeamConfiguration)

    @pytest.mark.asyncio
    async def test_get_team_reads_the_newest_of_several(self, client):
        """A default team cannot be deleted, so re-upload duplicates it (#54).

        `delete_team` refuses on `is_default`, and the post-provision script
        warns and uploads anyway -- a second document with the same team_id
        under a new partition key. Both stay live and every re-deploy adds
        another. Without an order, a configuration change lands on one
        deployment and silently does nothing on the next.
        """
        client.query_items.return_value = [Mock(spec=TeamConfiguration)]

        await client.get_team("test_team_id")

        query = client.query_items.call_args[0][0]
        assert "ORDER BY c._ts DESC" in query, (
            "get_team does not order, so which of several documents with this "
            "team_id is returned is whatever Cosmos hands back first"
        )

    @pytest.mark.asyncio
    async def test_get_team_not_found(self, client):
        """Test getting a team when not found."""
        client.query_items.return_value = []
        
        result = await client.get_team("test_team_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_team_by_id(self, client):
        """Test getting a team by document ID (same as get_team)."""
        mock_team = Mock(spec=TeamConfiguration)
        client.query_items.return_value = [mock_team]
        
        result = await client.get_team_by_id("test_team_id")
        
        assert result == mock_team
    
    @pytest.mark.asyncio
    async def test_get_all_teams(self, client):
        """Test getting all teams."""
        mock_teams = [Mock(spec=TeamConfiguration), Mock(spec=TeamConfiguration)]
        client.query_items.return_value = mock_teams
        
        result = await client.get_all_teams()
        
        assert result == mock_teams
        expected_query = "SELECT * FROM c WHERE c.data_type=@data_type AND (c.user_id=@user_id OR c.is_default=true) ORDER BY c.created DESC"
        expected_params = [
            {"name": "@data_type", "value": DataType.team_config},
            {"name": "@user_id", "value": "test_user"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, TeamConfiguration)
    
    @pytest.mark.asyncio
    async def test_delete_team_success(self, client):
        """Test successful team deletion."""
        mock_team = Mock(spec=TeamConfiguration)
        mock_team.id = "test_id"
        mock_team.session_id = "test_session"
        mock_team.is_default = False
        
        # Mock get_team to return the team
        with patch.object(client, 'get_team', return_value=mock_team):
            result = await client.delete_team("test_team_id")
        
        assert result is True
        client.delete_item.assert_called_once_with(item_id="test_id", partition_key="test_session")
    
    @pytest.mark.asyncio
    async def test_delete_team_not_found(self, client):
        """Test team deletion when team not found."""
        # Mock get_team to return None
        with patch.object(client, 'get_team', return_value=None):
            result = await client.delete_team("test_team_id")
        
        assert result is False
        client.delete_item.assert_not_called()


class TestCosmosDBCurrentTeamOperations:
    """Test CosmosDB current team operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_get_current_team_found(self, client):
        """Test getting current team when found."""
        mock_current_team = Mock(spec=UserCurrentTeam)
        client.query_items.return_value = [mock_current_team]
        
        result = await client.get_current_team("test_user_id")
        
        assert result == mock_current_team
        expected_query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        expected_params = [
            {"name": "@data_type", "value": DataType.user_current_team},
            {"name": "@user_id", "value": "test_user_id"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, UserCurrentTeam)
    
    @pytest.mark.asyncio
    async def test_get_current_team_not_found(self, client):
        """Test getting current team when not found."""
        client.query_items.return_value = []
        
        result = await client.get_current_team("test_user_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_current_team_no_container(self, client):
        """Test getting current team when container is None."""
        client.container = None
        
        result = await client.get_current_team("test_user_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_current_team(self, client):
        """Test setting current team."""
        mock_current_team = Mock(spec=UserCurrentTeam)
        
        await client.set_current_team(mock_current_team)
        
        client.add_item.assert_called_once_with(mock_current_team)
    
    @pytest.mark.asyncio
    async def test_update_current_team(self, client):
        """Test updating current team."""
        mock_current_team = Mock(spec=UserCurrentTeam)
        
        await client.update_current_team(mock_current_team)
        
        client.update_item.assert_called_once_with(mock_current_team)
    
    @pytest.mark.asyncio
    async def test_delete_current_team(self, client):
        """Test deleting current team."""
        mock_docs = [{"id": "doc1", "session_id": "session1"}, {"id": "doc2", "session_id": "session2"}]
        
        # Mock the container.query_items to return an async iterable
        async def async_gen():
            for doc in mock_docs:
                yield doc
        
        client.container.query_items = Mock(return_value=async_gen())
        
        result = await client.delete_current_team("test_user_id")
        
        assert result is True
        assert client.container.delete_item.call_count == 2
        client.container.delete_item.assert_any_call("doc1", partition_key="session1")
        client.container.delete_item.assert_any_call("doc2", partition_key="session2")


class TestCosmosDBChatDeletion:
    """**Chat deletion** — the whole session partition, scoped to its owner.

    #75 / ADR-026. The primitive beside this one, `delete_plan_by_plan_id`,
    takes a single plan document, is not scoped by `user_id` and returns
    ``True`` whatever happened. This is the operation the surface's delete
    control is allowed to mean, and every one of those three differences is
    asserted here.

    Both reads go to the container **raw**, and that is load-bearing rather
    than incidental — see `test_a_status_this_build_cannot_read_is_running`
    and `test_a_store_failure_is_not_reported_as_a_missing_chat`. So the
    container is what these tests stub.
    """

    @pytest.fixture
    def client(self):
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user",
        )
        client._initialized = True
        client.container = AsyncMock()
        return client

    @staticmethod
    def _cosmos(client, latest=None, partition=None, raises=None):
        """Stand in for the container's two reads.

        Told apart by what they project: the first asks for the latest plan's
        ``overall_status``, the second enumerates the partition. ``raises`` is
        raised while iterating the first, which is where the Azure SDK
        surfaces a store failure.
        """

        def query_items(**kwargs):
            status_read = "overall_status" in kwargs["query"]

            async def cursor():
                if status_read and raises is not None:
                    raise raises
                for row in (latest if status_read else partition) or []:
                    yield row

            return cursor()

        client.container.query_items = Mock(side_effect=query_items)

    @staticmethod
    def _status_query(client):
        for call in client.container.query_items.call_args_list:
            if "overall_status" in call.kwargs["query"]:
                return call.kwargs
        raise AssertionError("delete_chat never read the chat's latest status")

    @staticmethod
    def _sweep_query(client):
        for call in client.container.query_items.call_args_list:
            if "overall_status" not in call.kwargs["query"]:
                return call.kwargs
        raise AssertionError("delete_chat never enumerated the partition")

    @pytest.mark.asyncio
    async def test_reads_the_latest_status_scoped_to_this_user(self, client):
        # The `user_id` predicate is the whole of the authorization: one
        # associate may not delete another's chat, and there is nothing else
        # standing between a session id and an irreversible sweep.
        self._cosmos(client, latest=[{"overall_status": "completed"}], partition=[])

        await client.delete_chat("session-1")

        read = self._status_query(client)
        assert "c.session_id=@session_id" in read["query"]
        assert "c.user_id=@user_id" in read["query"]
        assert "ORDER BY c._ts DESC" in read["query"]
        assert {"name": "@user_id", "value": "test_user"} in read["parameters"]
        assert {"name": "@session_id", "value": "session-1"} in read["parameters"]

    @pytest.mark.asyncio
    async def test_a_chat_this_user_does_not_own_is_no_chat_at_all(self, client):
        # The read above comes back empty for a session that does not exist and
        # for one belonging to somebody else alike, and both are reported the
        # same way: saying "that is not yours" says the chat exists.
        self._cosmos(client, latest=[])

        result = await client.delete_chat("session-someone-else")

        assert result.outcome is DeletionOutcome.no_such_chat
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_running_chat_is_kept(self, client):
        self._cosmos(client, latest=[{"overall_status": PlanStatus.in_progress.value}])

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_chats_state_is_its_latest_plans(self, client):
        # A Chat is a Session and holds more than one Plan (#71), and its state
        # is the latest one's — the read is newest-first, so a finished older
        # turn beneath a running escalation must not make the chat deletable.
        self._cosmos(
            client,
            latest=[
                {"overall_status": PlanStatus.in_progress.value},
                {"overall_status": PlanStatus.completed.value},
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running

    @pytest.mark.asyncio
    async def test_a_status_this_build_cannot_read_is_running(self, client):
        # Why the status is read as text rather than through `Plan`.
        # `query_items` validates each document into a model and **skips** the
        # ones that will not parse, so a newest plan carrying a status this
        # build does not know would vanish from the read and promote an older,
        # completed turn to "the chat's state" — deleting a live conversation
        # through the very rule written to keep it. Raw, `is_running` sees the
        # unknown status and fails closed, which is what it is for.
        self._cosmos(
            client,
            latest=[{"overall_status": "quiescing"}, {"overall_status": "completed"}],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_plan_reporting_no_status_at_all_is_running(self, client):
        self._cosmos(client, latest=[{}])

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running

    @pytest.mark.asyncio
    async def test_a_store_failure_is_not_reported_as_a_missing_chat(self, client):
        # The other reason this read does not go through `query_items`: that
        # helper logs a Cosmos failure and returns `[]`, which is
        # indistinguishable here from "no such chat". The associate would be
        # told their conversation does not exist during an outage — and the
        # route would answer 404 to a chat that is sitting in Cosmos.
        self._cosmos(client, raises=RuntimeError("Cosmos is unavailable"))

        with pytest.raises(RuntimeError):
            await client.delete_chat("session-1")

        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_takes_every_document_in_the_partition(self, client):
        # Plans, steps, transcript, `m_plan`, Troubleshooting record, Simulated
        # ticket and Session state all live in this one partition. Deleting
        # only the plan is what ADR-026 rejected: the conversation would
        # survive a control that promised to delete it.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed"}],
            partition=[
                {"id": "plan-1", "user_id": "test_user"},
                {"id": "step-1", "user_id": "test_user"},
                {"id": "agent-message-1", "user_id": "test_user"},
                {"id": "m_plan-1", "user_id": "test_user"},
                {"id": "troubleshooting:session-1"},
                {"id": "service_ticket:session-1"},
                {"id": "session_state:session-1"},
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.deleted
        assert result.deleted == 7
        assert client.container.delete_item.call_count == 7
        client.container.delete_item.assert_any_call(
            "session_state:session-1", partition_key="session-1"
        )

    @pytest.mark.asyncio
    async def test_the_sweep_is_not_narrowed_by_data_type(self, client):
        # Whatever else has been written into a chat's partition since — the
        # sweep is the partition's, so a record added later goes with the chat
        # rather than outliving it as an orphan nobody can reach.
        self._cosmos(client, latest=[{"overall_status": "completed"}], partition=[])

        await client.delete_chat("session-1")

        sweep = self._sweep_query(client)
        assert "c.session_id=@session_id" in sweep["query"]
        assert "data_type" not in sweep["query"]

    @pytest.mark.asyncio
    async def test_a_partition_holding_another_users_record_is_refused(self, client):
        # Found by review. One plan of this user's proves the *chat* is theirs;
        # it does not prove the *partition* is, and the sweep is the
        # partition's. `process_request` takes a caller-supplied session id, so
        # a second user writing one settled plan into somebody else's session
        # would pass the ownership read and then delete both conversations.
        # The whole partition is therefore read before anything is deleted —
        # refusing halfway is a half-deleted chat.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed"}],
            partition=[
                {"id": "plan-1", "user_id": "test_user"},
                {"id": "plan-2", "user_id": "another_associate"},
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.not_yours
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_record_carrying_no_owner_belongs_to_the_chat(self, client):
        # The Session state, the Troubleshooting record and the Simulated
        # ticket are written against the session rather than against a user, so
        # "no owner" must not be read as "somebody else's" — that would refuse
        # every real chat.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed"}],
            partition=[{"id": "session_state:session-1", "user_id": None}],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.deleted
        assert result.deleted == 1

    @pytest.mark.asyncio
    async def test_a_sweep_that_left_something_behind_does_not_report_success(
        self, client
    ):
        # The failure `delete_plan_by_plan_id` has and must not pass on: it
        # logs a warning and returns `True` regardless. A chat half-deleted is
        # still in Cosmos and the associate may not be told otherwise.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed"}],
            partition=[{"id": "plan-1"}, {"id": "step-1"}],
        )
        client.container.delete_item = AsyncMock(
            side_effect=[None, Exception("conflict")]
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.incomplete
        assert result.deleted == 1
        assert result.failed == 1


class TestDeleteAllChats:
    """The list-level control, at the store (#76, ADR-026).

    "The same primitive applied to a set" is literal here: this enumerates the
    associate's Chats and hands each one to ``delete_chat``, so every chat that
    goes goes on exactly the terms the single delete established — the whole
    session partition, scoped to this ``user_id``, and a running chat kept by
    the same fail-closed rule. The enumeration is the only new decision, and it
    is what these tests are mostly about.
    """

    @pytest.fixture
    def client(self):
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user",
        )
        client._initialized = True
        client.container = AsyncMock()
        return client

    @staticmethod
    def _sessions(client, rows, raises=None):
        """Stand in for the read that finds this associate's Chats."""

        def query_items(**kwargs):
            async def cursor():
                if raises is not None:
                    raise raises
                for row in rows:
                    yield row

            return cursor()

        client.container.query_items = Mock(side_effect=query_items)

    @pytest.mark.asyncio
    async def test_every_chat_of_this_users_is_swept_by_the_single_delete(
        self, client
    ):
        # Not a second sweep written beside the first. `delete_chat` is where
        # ownership is proved twice, where a running chat is kept and where the
        # partition is enumerated in full before anything goes; a bulk path
        # that re-implemented any of that would be a second place for all three
        # to be forgotten.
        self._sessions(
            client, [{"session_id": "session-1"}, {"session_id": "session-2"}]
        )
        client.delete_chat = AsyncMock(
            side_effect=[
                ChatDeletion.swept(deleted=4, failed=0),
                ChatDeletion.swept(deleted=3, failed=0),
            ]
        )

        result = await client.delete_all_chats()

        assert client.delete_chat.await_args_list == [
            call("session-1"),
            call("session-2"),
        ]
        assert result.deleted == ("session-1", "session-2")
        assert result.documents_deleted == 7

    @pytest.mark.asyncio
    async def test_only_this_users_chats_are_found(self, client):
        # The whole of the authorization, and the reason the enumeration is not
        # the panel's list handed back: the panel reads plans by *team*, and a
        # control that swept whatever the browser listed would let one
        # associate clear another's history.
        self._sessions(client, [])

        await client.delete_all_chats()

        read = client.container.query_items.call_args.kwargs
        assert "c.user_id=@user_id" in read["query"]
        assert {"name": "@user_id", "value": "test_user"} in read["parameters"]

    @pytest.mark.asyncio
    async def test_a_chat_is_swept_once_however_many_plans_it_holds(self, client):
        # A Chat is a Session and holds more than one Plan (#71) — the
        # walkthrough's centrepiece pair is one chat with two. Deduped here
        # rather than left to the store's `DISTINCT`, because the second sweep
        # of an already-deleted partition reports `no_such_chat` and the
        # outcome would count a phantom failure.
        self._sessions(
            client,
            [
                {"session_id": "session-1"},
                {"session_id": "session-2"},
                {"session_id": "session-1"},
            ],
        )
        client.delete_chat = AsyncMock(return_value=ChatDeletion.swept(1, 0))

        result = await client.delete_all_chats()

        assert client.delete_chat.await_args_list == [
            call("session-1"),
            call("session-2"),
        ]
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_a_running_chat_is_kept_and_the_rest_still_go(self, client):
        # The one rule that makes this control honest. Refusing the whole
        # operation because something is running makes it useless at exactly
        # the moment a presenter wants it.
        self._sessions(
            client, [{"session_id": "session-1"}, {"session_id": "session-2"}]
        )
        client.delete_chat = AsyncMock(
            side_effect=[
                ChatDeletion(DeletionOutcome.still_running),
                ChatDeletion.swept(deleted=3, failed=0),
            ]
        )

        result = await client.delete_all_chats()

        assert result.deleted == ("session-2",)
        assert result.kept_running == 1

    @pytest.mark.asyncio
    async def test_one_chat_that_will_not_go_does_not_stop_the_others(self, client):
        # Stopping at the first failure would leave the list half-cleared with
        # no account of where it stopped, which is worse than the failure.
        self._sessions(
            client,
            [
                {"session_id": "session-1"},
                {"session_id": "session-2"},
                {"session_id": "session-3"},
            ],
        )
        client.delete_chat = AsyncMock(
            side_effect=[
                ChatDeletion.swept(deleted=2, failed=1),
                Exception("Cosmos is having a moment"),
                ChatDeletion.swept(deleted=5, failed=0),
            ]
        )

        result = await client.delete_all_chats()

        assert result.deleted == ("session-3",)
        assert result.failed == 2
        assert result.status == "incomplete"

    @pytest.mark.asyncio
    async def test_a_store_failure_is_not_reported_as_an_empty_list(self, client):
        # An outage while enumerating would otherwise come back as "there was
        # nothing to delete", and the panel would tell the presenter their
        # history is gone while every chat sits in Cosmos. The same reading
        # `delete_chat` refuses, for the same reason.
        self._sessions(client, [], raises=Exception("Cosmos unavailable"))

        with pytest.raises(Exception, match="Cosmos unavailable"):
            await client.delete_all_chats()

    @pytest.mark.asyncio
    async def test_an_empty_history_is_a_result_rather_than_an_error(self, client):
        self._sessions(client, [])

        result = await client.delete_all_chats()

        assert result.deleted == ()
        assert result.status == "deleted"


class TestCosmosDBDataManagement:
    """Test CosmosDB data management operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.query_items = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_get_data_by_type_with_mapped_class(self, client):
        """Test getting data by type with mapped model class."""
        mock_plans = [Mock(spec=Plan), Mock(spec=Plan)]
        client.query_items.return_value = mock_plans
        
        result = await client.get_data_by_type(DataType.plan)
        
        assert result == mock_plans
        expected_query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        expected_params = [
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@user_id", "value": "test_user"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, Plan)
    
    @pytest.mark.asyncio
    async def test_get_data_by_type_with_unmapped_class(self, client):
        """Test getting data by type with unmapped model class."""
        mock_data = [Mock(spec=BaseDataModel)]
        client.query_items.return_value = mock_data
        
        result = await client.get_data_by_type("unknown_type")
        
        assert result == mock_data
        expected_query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        expected_params = [
            {"name": "@data_type", "value": "unknown_type"},
            {"name": "@user_id", "value": "test_user"},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, BaseDataModel)


class TestCosmosDBAgentMessageOperations:
    """Test CosmosDB agent message operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_add_agent_message(self, client):
        """Test adding an agent message."""
        mock_message = Mock(spec=AgentMessageData)
        
        await client.add_agent_message(mock_message)
        
        client.add_item.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_update_agent_message(self, client):
        """Test updating an agent message."""
        mock_message = Mock(spec=AgentMessageData)
        
        await client.update_agent_message(mock_message)
        
        client.update_item.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_get_agent_messages(self, client):
        """Test getting agent messages by plan ID."""
        mock_messages = [Mock(spec=AgentMessageData), Mock(spec=AgentMessageData)]
        client.query_items.return_value = mock_messages
        
        result = await client.get_agent_messages("test_plan_id")
        
        assert result == mock_messages
        expected_query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type ORDER BY c._ts ASC"
        expected_params = [
            {"name": "@plan_id", "value": "test_plan_id"},
            {"name": "@data_type", "value": DataType.m_plan_message},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, AgentMessageData)


class TestCosmosDBMiscellaneousOperations:
    """Test CosmosDB miscellaneous operations."""
    
    @pytest.fixture
    def client(self):
        """Create an initialized CosmosDB client for testing."""
        client = CosmosDBClient(
            endpoint="https://test.documents.azure.com:443/",
            credential="test_credential",
            database_name="test_db",
            container_name="test_container",
            session_id="test_session",
            user_id="test_user"
        )
        client._initialized = True
        client.container = AsyncMock()
        client.add_item = AsyncMock()
        client.update_item = AsyncMock()
        client.query_items = AsyncMock()
        client.delete_team_agent = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_delete_plan_by_plan_id(self, client):
        """Test deleting a plan by plan ID."""
        mock_docs = [{"id": "plan1", "session_id": "session1"}]
        
        # Mock the container.query_items to return an async iterable
        async def async_gen():
            for doc in mock_docs:
                yield doc
        
        client.container.query_items = Mock(return_value=async_gen())
        client.container.delete_item = AsyncMock()
        
        result = await client.delete_plan_by_plan_id("test_plan_id")
        
        assert result is True
        client.container.delete_item.assert_called_once_with("plan1", partition_key="session1")
    
    @pytest.mark.asyncio
    async def test_add_mplan(self, client):
        """Test adding an mplan."""
        mock_mplan = Mock()
        
        await client.add_mplan(mock_mplan)
        
        client.add_item.assert_called_once_with(mock_mplan)
    
    @pytest.mark.asyncio
    async def test_update_mplan(self, client):
        """Test updating an mplan."""
        mock_mplan = Mock()
        
        await client.update_mplan(mock_mplan)
        
        client.update_item.assert_called_once_with(mock_mplan)
    
    @pytest.mark.asyncio
    async def test_get_mplan(self, client):
        """Test getting an mplan by plan ID."""
        mock_mplan = Mock()
        client.query_items.return_value = [mock_mplan]
        
        result = await client.get_mplan("test_plan_id")
        
        assert result == mock_mplan
        expected_query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type"
        expected_params = [
            {"name": "@plan_id", "value": "test_plan_id"},
            {"name": "@data_type", "value": DataType.m_plan},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, MPlan)
    
    @pytest.mark.asyncio
    async def test_add_team_agent(self, client):
        """Test adding a team agent."""
        mock_team_agent = Mock(spec=CurrentTeamAgent)
        mock_team_agent.team_id = "test_team"
        mock_team_agent.agent_name = "test_agent"
        
        await client.add_team_agent(mock_team_agent)
        
        client.delete_team_agent.assert_called_once_with("test_team", "test_agent")
        client.add_item.assert_called_once_with(mock_team_agent)
    
    @pytest.mark.asyncio
    async def test_get_team_agent(self, client):
        """Test getting a team agent."""
        mock_team_agent = Mock(spec=CurrentTeamAgent)
        client.query_items.return_value = [mock_team_agent]
        
        result = await client.get_team_agent("test_team", "test_agent")
        
        assert result == mock_team_agent
        expected_query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type AND c.agent_name=@agent_name"
        expected_params = [
            {"name": "@team_id", "value": "test_team"},
            {"name": "@agent_name", "value": "test_agent"},
            {"name": "@data_type", "value": DataType.current_team_agent},
        ]
        client.query_items.assert_called_once_with(expected_query, expected_params, CurrentTeamAgent)


# Helper class for async iteration in tests
class AsyncIteratorMock:
    """Mock async iterator for testing."""
    
    def __init__(self, items):
        self.items = items
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])