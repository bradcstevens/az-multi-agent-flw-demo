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
from backend.common.database.cosmosdb import CosmosDBClient, MatchConditions
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
from chat.settle import SettleOutcome
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


def _settled_chat(status="completed", etag="etag-1"):
    """A chat whose latest plan has settled, described consistently.

    The status read and the partition enumeration are two reads of the same
    store, so a fixture that lets them disagree — a latest plan the
    enumeration never saw — is the concurrency case, not the ordinary one. It
    has its own tests; every other test here starts from a chat that is simply
    settled.
    """
    return {
        "latest": [{"overall_status": status, "id": "plan-1", "_etag": etag}],
        "partition": [{"id": "plan-1", "user_id": "test_user"}],
    }


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
    def _cosmos(
        client,
        latest=None,
        partition=None,
        raises=None,
        latest_after=None,
        remaining=0,
    ):
        """Stand in for the container's reads.

        Told apart by what they project: a status read asks for the latest
        plan's ``overall_status``, the verification read counts what is left in
        the partition, and the remaining one enumerates it. ``raises`` is
        raised while iterating the first status read, which is where the Azure
        SDK surfaces a store failure.

        The status read happens **twice** — once to refuse early and once after
        the partition has been enumerated (the concurrency guard). ``latest``
        answers the first, ``latest_after`` the second when a test wants the
        chat to change under the sweep; otherwise the store answers the same
        thing both times. ``remaining`` is what the verification read finds
        once the deletes are done: anything but ``0`` is a document written
        into the partition while the sweep ran.
        """
        status_reads = {"n": 0}

        def query_items(**kwargs):
            query = kwargs["query"]
            status_read = "overall_status" in query
            verification_read = "COUNT" in query

            if status_read:
                status_reads["n"] += 1
                rows = latest
                if status_reads["n"] > 1 and latest_after is not None:
                    rows = latest_after
            elif verification_read:
                rows = [remaining]
            else:
                rows = partition

            first_status_read = status_read and status_reads["n"] == 1

            async def cursor():
                if first_status_read and raises is not None:
                    raise raises
                for row in rows or []:
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
            query = call.kwargs["query"]
            if "overall_status" not in query and "COUNT" not in query:
                return call.kwargs
        raise AssertionError("delete_chat never enumerated the partition")

    @pytest.mark.asyncio
    async def test_reads_the_latest_status_scoped_to_this_user(self, client):
        # The `user_id` predicate is the whole of the authorization: one
        # associate may not delete another's chat, and there is nothing else
        # standing between a session id and an irreversible sweep.
        self._cosmos(client, **_settled_chat())

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
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
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
        self._cosmos(client, **_settled_chat())

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
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[
                {"id": "plan-1", "user_id": "test_user"},
                {"id": "session_state:session-1", "user_id": None},
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.deleted
        assert result.deleted == 2
        client.container.delete_item.assert_any_call(
            "session_state:session-1", partition_key="session-1"
        )

    @pytest.mark.asyncio
    async def test_a_sweep_that_left_something_behind_does_not_report_success(
        self, client
    ):
        # The failure `delete_plan_by_plan_id` has and must not pass on: it
        # logs a warning and returns `True` regardless. A chat half-deleted is
        # still in Cosmos and the associate may not be told otherwise.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[{"id": "plan-1"}, {"id": "step-1"}],
        )
        client.container.delete_item = AsyncMock(
            side_effect=[None, Exception("conflict")]
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.incomplete
        assert result.deleted == 1
        assert result.failed == 1


class _PreconditionFailed(Exception):
    """Stands in for ``CosmosAccessConditionFailedError``.

    The real class cannot be imported here — this module mocks ``azure.cosmos``
    out wholesale so the store can be tested without an SDK — and what the
    store actually reads is the HTTP status the SDK puts on it. 412 is the
    conditional delete being refused: the document moved.
    """

    status_code = 412


class TestChatDeletionRaces:
    """The sweep against a chat that changes while it runs (#76, review).

    The status check, the enumeration and the deletes are three operations, and
    a Chat is a live thing: ``process_request`` can write a new Plan into the
    session between any two of them. ADR-026 says a running Chat cannot be
    deleted, so "the chat was settled when we looked" is not enough — these are
    the guards that make the sentence true of the moment the documents actually
    go, and the one case they cannot prevent (a document written *behind* the
    sweep) is reported as ``incomplete`` rather than as a deleted chat.
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

    _cosmos = staticmethod(
        lambda client, **kwargs: TestCosmosDBChatDeletion._cosmos(client, **kwargs)
    )

    @pytest.mark.asyncio
    async def test_the_latest_plan_goes_first_and_only_if_it_has_not_changed(
        self, client
    ):
        # The conditional delete is the guard. Between the status read and the
        # first `delete_item` the plan can settle *or* start again, and Cosmos
        # is the only party that can see the difference: the plan is deleted on
        # the `_etag` the status read observed, so a plan that moved refuses
        # the delete instead of taking the conversation with it.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[
                {"id": "step-1", "user_id": "test_user"},
                {"id": "plan-1", "user_id": "test_user"},
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.deleted
        first = client.container.delete_item.call_args_list[0]
        assert first.args[0] == "plan-1"
        assert first.kwargs["etag"] == "e1"
        assert first.kwargs["match_condition"] is MatchConditions.IfNotModified

    @pytest.mark.asyncio
    async def test_a_plan_that_moved_under_the_sweep_keeps_the_whole_chat(
        self, client
    ):
        # The precondition failure arrives on the *first* delete, which is why
        # the latest plan goes first: nothing else has been touched yet, so the
        # chat is kept whole rather than left half-swept.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[
                {"id": "plan-1", "user_id": "test_user"},
                {"id": "step-1", "user_id": "test_user"},
            ],
        )
        client.container.delete_item = AsyncMock(side_effect=_PreconditionFailed())

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        assert result.deleted == 0
        assert client.container.delete_item.await_count == 1

    @pytest.mark.asyncio
    async def test_a_turn_that_starts_while_the_partition_is_read_keeps_the_chat(
        self, client
    ):
        # A new Plan written after the enumeration is not in the sweep's list
        # at all, so its `_etag` cannot refuse anything — but it *is* the
        # chat's latest plan now, and the chat is therefore running. The status
        # is read a second time, after the enumeration, for exactly this.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[{"id": "plan-1", "user_id": "test_user"}],
            latest_after=[
                {
                    "overall_status": PlanStatus.in_progress.value,
                    "id": "plan-2",
                    "_etag": "e2",
                }
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_latest_plan_the_enumeration_never_saw_keeps_the_chat(
        self, client
    ):
        # The same race with a settled status on the newcomer: a plan the sweep
        # has no id for would survive a delete the surface reported as
        # complete. Fail-closed, like every other "cannot tell" here.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[{"id": "plan-1", "user_id": "test_user"}],
            latest_after=[
                {"overall_status": "completed", "id": "plan-2", "_etag": "e2"}
            ],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_latest_plan_the_store_did_not_describe_is_kept(self, client):
        # No `_etag` means no conditional delete, which means no guard. A chat
        # this build cannot delete safely is kept, for the reason
        # `is_running` keeps one whose status it cannot read.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1"}],
            partition=[{"id": "plan-1", "user_id": "test_user"}],
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.still_running
        client.container.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_document_written_behind_the_sweep_is_not_a_deleted_chat(
        self, client
    ):
        # The race the guards above cannot close: a record written into the
        # partition after its enumeration and before the last delete. The
        # partition is counted once the sweep is done, and anything still in it
        # makes this `incomplete` — the chat is still in Cosmos, and ADR-026
        # does not let the surface say otherwise.
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[{"id": "plan-1", "user_id": "test_user"}],
            remaining=1,
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.incomplete
        assert result.deleted == 1
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_an_empty_partition_afterwards_is_the_chat_gone(self, client):
        self._cosmos(
            client,
            latest=[{"overall_status": "completed", "id": "plan-1", "_etag": "e1"}],
            partition=[{"id": "plan-1", "user_id": "test_user"}],
            remaining=0,
        )

        result = await client.delete_chat("session-1")

        assert result.outcome is DeletionOutcome.deleted
        assert result.deleted == 1


class TestTheSettleWrite:
    """The server settles the turn it ended (#157, ADR-043).

    One operation, and every writer of a **Settled status** goes through it:
    write this terminal status onto the session's latest **Plan record**, unless
    that Plan already reached a Settled status. Before this, the only writer
    anywhere was the browser echoing `is_final` back through
    `POST /v4/agent_message` — so a finished turn's record was contingent on a
    socket, a tab and a fetch, and `failed` was written by nothing at all.

    The container is what these tests stub, for the reason `delete_chat`'s do:
    the status is read raw, because a plan this build cannot validate must not
    vanish from the read and promote an older one.
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
    def _cosmos(client, latest=None, raises=None, refuses=None):
        """Stand in for the one read and the one write.

        ``raises`` is raised while iterating the status read, which is where the
        Azure SDK surfaces a store failure; ``refuses`` is what the conditional
        write raises.
        """

        def query_items(**kwargs):
            async def cursor():
                if raises is not None:
                    raise raises
                for row in latest or []:
                    yield row

            return cursor()

        client.container.query_items = Mock(side_effect=query_items)
        client.container.patch_item = AsyncMock(side_effect=refuses)

    @staticmethod
    def _running_plan(status=None, plan_id="plan-1", etag="etag-1"):
        row = {"id": plan_id}
        if status is not None:
            row["overall_status"] = status
        if etag is not None:
            row["_etag"] = etag
        return [row]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status",
        [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled],
    )
    async def test_a_turn_that_ended_reaches_its_terminal_status(
        self, client, status
    ):
        # `failed` and `canceled` among them: two statuses this system renders
        # and permits, and until ADR-043 and ADR-031 could not produce.
        self._cosmos(client, latest=self._running_plan(PlanStatus.in_progress.value))

        result = await client.settle_turn("session-1", status)

        assert result.outcome is SettleOutcome.settled
        assert result.status == status.value
        assert result.persisted is True
        written = client.container.patch_item.call_args
        assert written.kwargs["patch_operations"] == [
            {"op": "set", "path": "/overall_status", "value": status.value}
        ]

    @pytest.mark.asyncio
    async def test_the_write_targets_the_latest_plan_of_this_users(self, client):
        # The `user_id` predicate is the whole of the authorization, exactly as
        # it is for the delete: a session id is not a secret, and settling
        # somebody else's turn is writing a verdict onto a conversation this
        # caller cannot see. Newest-first because a Chat holds more than one
        # Plan (#71) and its state is the latest one's.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, plan_id="plan-9"),
        )

        await client.settle_turn("session-1", PlanStatus.completed)

        read = client.container.query_items.call_args.kwargs
        assert "c.session_id=@session_id" in read["query"]
        assert "c.user_id=@user_id" in read["query"]
        assert "ORDER BY c._ts DESC" in read["query"]
        assert {"name": "@user_id", "value": "test_user"} in read["parameters"]
        written = client.container.patch_item.call_args
        assert written.args[0] == "plan-9"
        assert written.kwargs["partition_key"] == "session-1"

    @pytest.mark.asyncio
    async def test_the_write_is_conditional_on_what_was_read(self, client):
        # Not read-then-clobber (ADR-043 decision 6). The `_etag` the status
        # read observed rides on the write, so a settle that landed in between
        # refuses this one instead of silently losing to a stale read.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, etag="e1"),
        )

        await client.settle_turn("session-1", PlanStatus.completed)

        written = client.container.patch_item.call_args
        assert written.kwargs["etag"] == "e1"
        assert written.kwargs["match_condition"] is MatchConditions.IfNotModified

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "already", [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled]
    )
    @pytest.mark.parametrize(
        "asked", [PlanStatus.completed, PlanStatus.failed, PlanStatus.canceled]
    )
    async def test_a_settled_status_is_never_overwritten(
        self, client, already, asked
    ):
        # Every terminal status against every other. A turn that failed after a
        # partial success, a late echo and #120's end-of-turn primitive all
        # converge on this one document, and the first true answer is the one
        # that stands: a record corrected into being wrong is worse than one
        # left alone.
        self._cosmos(client, latest=self._running_plan(already.value))

        result = await client.settle_turn("session-1", asked)

        assert result.outcome is SettleOutcome.already_settled
        assert result.status == already.value
        assert result.persisted is True
        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_chat_this_user_does_not_own_is_no_chat_at_all(self, client):
        # The read comes back empty for a session that does not exist and for
        # one belonging to somebody else alike.
        self._cosmos(client, latest=[])

        result = await client.settle_turn("session-someone-else", PlanStatus.completed)

        assert result.outcome is SettleOutcome.no_such_chat
        assert result.persisted is False
        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_plan_that_moved_under_the_write_keeps_what_it_moved_to(
        self, client
    ):
        # The 412 is the guard doing its job: another writer settled this turn
        # between the read and the write, and by the rule above theirs is the
        # answer that stands.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value),
            refuses=_PreconditionFailed(),
        )

        result = await client.settle_turn("session-1", PlanStatus.completed)

        assert result.outcome is SettleOutcome.lost_race
        assert result.persisted is False

    @pytest.mark.asyncio
    async def test_a_store_failure_is_not_reported_as_a_settled_turn(self, client):
        # The defect ADR-043 names, at the layer that could reintroduce it: a
        # write that did not land must not come back as one that did.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value),
            refuses=RuntimeError("Cosmos is unavailable"),
        )

        result = await client.settle_turn("session-1", PlanStatus.completed)

        assert result.outcome is SettleOutcome.refused
        assert result.persisted is False

    @pytest.mark.asyncio
    async def test_a_failed_read_is_not_reported_as_a_settled_turn_either(
        self, client
    ):
        self._cosmos(client, raises=RuntimeError("Cosmos is unavailable"))

        with pytest.raises(RuntimeError):
            await client.settle_turn("session-1", PlanStatus.completed)

        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_plan_the_store_did_not_describe_is_left_alone(self, client):
        # No `_etag` means no conditional write, which means no guard. A turn
        # this build cannot settle safely is left running, for the reason
        # `delete_chat` keeps a chat whose latest plan it cannot guard.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, etag=None),
        )

        result = await client.settle_turn("session-1", PlanStatus.completed)

        assert result.outcome is SettleOutcome.refused
        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_status_this_build_cannot_read_is_a_turn_still_running(
        self, client
    ):
        # `is_running` is fail-closed and this is the direction that makes it
        # so: a status the settled set does not recognise is not a turn that
        # ended, so settling it overwrites nothing the rule protects.
        self._cosmos(client, latest=self._running_plan("quiescing"))

        result = await client.settle_turn("session-1", PlanStatus.completed)

        assert result.outcome is SettleOutcome.settled

    @pytest.mark.asyncio
    async def test_a_plan_reporting_no_status_at_all_is_settled(self, client):
        self._cosmos(client, latest=self._running_plan(None))

        result = await client.settle_turn("session-1", PlanStatus.failed)

        assert result.outcome is SettleOutcome.settled

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status", [PlanStatus.in_progress, PlanStatus.approved, "error", None]
    )
    async def test_only_a_settled_status_settles_a_turn(self, client, status):
        # Refused before the store is touched. `error` is the orchestration's
        # wire word and not a fourth member of the settled set (ADR-043
        # decision 4); `in_progress` would be a way of un-ending a turn.
        self._cosmos(client, latest=self._running_plan(PlanStatus.in_progress.value))

        with pytest.raises(ValueError):
            await client.settle_turn("session-1", status)

        client.container.query_items.assert_not_called()
        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_turn_settles_the_plan_it_ran(self, client):
        # The caller names the Plan its turn ran, and the latest Plan is that
        # one: the ordinary case, and the write goes ahead.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, plan_id="plan-1"),
        )

        result = await client.settle_turn(
            "session-1", PlanStatus.completed, "plan-1"
        )

        assert result.outcome is SettleOutcome.settled

    @pytest.mark.asyncio
    async def test_a_turn_that_ended_late_never_settles_its_successor(self, client):
        # `process_request` writes the next turn's Plan *before* it cancels the
        # orchestration in flight, so a turn finishing inside that window finds
        # a Plan at the top of the session that belongs to an answer which has
        # not started. Settling it would stamp a terminal status onto a live
        # turn — the one direction of error ADR-043 exists to prevent — and
        # would make a running Chat deletable on the way past.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, plan_id="plan-2"),
        )

        result = await client.settle_turn(
            "session-1", PlanStatus.completed, "plan-1"
        )

        assert result.outcome is SettleOutcome.superseded
        assert result.persisted is False
        client.container.patch_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_superseded_turn_is_refused_even_by_a_settled_latest_plan(
        self, client
    ):
        # Checked before the never-overwrite rule, so the outcome names the
        # reason a reader needs: this turn had nothing of its own to settle,
        # rather than "somebody settled it first".
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.completed.value, plan_id="plan-2"),
        )

        result = await client.settle_turn("session-1", PlanStatus.failed, "plan-1")

        assert result.outcome is SettleOutcome.superseded

    @pytest.mark.asyncio
    async def test_a_session_scoped_caller_names_no_plan(self, client):
        # #120's end-of-turn primitive and #159's reconciliation settle a
        # *session*, and have no plan id to be held to. Naming none is not
        # naming the wrong one.
        self._cosmos(
            client,
            latest=self._running_plan(PlanStatus.in_progress.value, plan_id="plan-7"),
        )

        result = await client.settle_turn("session-1", PlanStatus.canceled)

        assert result.outcome is SettleOutcome.settled
        assert client.container.patch_item.call_args.args[0] == "plan-7"


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

        result = await client.delete_all_chats(team_id="team-1")

        assert client.delete_chat.await_args_list == [
            call("session-1"),
            call("session-2"),
        ]
        assert result.deleted == ("session-1", "session-2")
        assert result.documents_deleted == 7

    @pytest.mark.asyncio
    async def test_only_this_users_chats_are_found(self, client):
        # The whole of the authorization, and the reason the enumeration is not
        # the panel's list handed back: a control that swept whatever the
        # browser named would let one associate clear another's history.
        self._sessions(client, [])

        await client.delete_all_chats(team_id="team-1")

        read = client.container.query_items.call_args.kwargs
        assert "c.user_id=@user_id" in read["query"]
        assert {"name": "@user_id", "value": "test_user"} in read["parameters"]

    @pytest.mark.asyncio
    async def test_the_sweep_is_the_list_that_was_confirmed(self, client):
        # Found by review. The panel lists chats by *team*
        # (`get_all_plans_by_team_id`) and the confirmation counts that list,
        # so an enumeration scoped only by `user_id` would destroy chats the
        # dialog never mentioned — an irreversible action reaching past what
        # the presenter agreed to. The two reads answer the same question, so
        # they carry the same predicate.
        self._sessions(client, [])

        await client.delete_all_chats(team_id="team-1")

        read = client.container.query_items.call_args.kwargs
        assert "c.team_id=@team_id" in read["query"]
        assert {"name": "@team_id", "value": "team-1"} in read["parameters"]

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

        result = await client.delete_all_chats(team_id="team-1")

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

        result = await client.delete_all_chats(team_id="team-1")

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

        result = await client.delete_all_chats(team_id="team-1")

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
            await client.delete_all_chats(team_id="team-1")

    @pytest.mark.asyncio
    async def test_an_empty_history_is_a_result_rather_than_an_error(self, client):
        self._sessions(client, [])

        result = await client.delete_all_chats(team_id="team-1")

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