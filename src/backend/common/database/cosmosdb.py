"""CosmosDB implementation of the database interface."""

import datetime
import logging
from typing import Any, Dict, List, Optional, Type

from models.plan_models import MPlan
from azure.core import MatchConditions
from azure.cosmos.aio import CosmosClient
from azure.cosmos.aio._database import DatabaseProxy

from chat.deletion import ChatDeletion, ChatsDeletion, DeletionOutcome, is_running

from ..models.messages import (
    AgentMessage,
    AgentMessageData,
    BaseDataModel,
    CurrentTeamAgent,
    DataType,
    Plan,
    Step,
    TeamConfiguration,
    UserCurrentTeam,
)
from .database_base import DatabaseBase

# What Cosmos answers a conditional write it refused. Read off the status
# rather than by catching `CosmosAccessConditionFailedError`, so the sweep's
# guard does not depend on which of the SDK's error classes carries it.
PRECONDITION_FAILED = 412


class CosmosDBClient(DatabaseBase):
    """CosmosDB implementation of the database interface."""

    MODEL_CLASS_MAPPING = {
        DataType.plan: Plan,
        DataType.step: Step,
        DataType.agent_message: AgentMessage,
        DataType.team_config: TeamConfiguration,
        DataType.user_current_team: UserCurrentTeam,
    }

    def __init__(
        self,
        endpoint: str,
        credential: any,
        database_name: str,
        container_name: str,
        session_id: str = "",
        user_id: str = "",
    ):
        self.endpoint = endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        self.session_id = session_id
        self.user_id = user_id

        self.logger = logging.getLogger(__name__)
        self.client = None
        self.database = None
        self.container = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the CosmosDB client and create container if needed."""
        try:
            if not self._initialized:
                self.client = CosmosClient(
                    url=self.endpoint, credential=self.credential
                )
                self.database = self.client.get_database_client(self.database_name)

                self.container = await self._get_container(
                    self.database, self.container_name
                )
                self._initialized = True

        except Exception as e:
            self.logger.error("Failed to initialize CosmosDB: %s", str(e))
            raise

    # Helper Methods
    async def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if not self._initialized:
            await self.initialize()

    async def _get_container(self, database: DatabaseProxy, container_name):
        try:
            return database.get_container_client(container_name)

        except Exception as e:
            self.logger.error("Failed to Get cosmosdb container", error=str(e))
            raise

    async def close(self) -> None:
        """Close the CosmosDB connection."""
        if self.client:
            await self.client.close()
            self.logger.info("Closed CosmosDB connection")

    # Core CRUD Operations
    async def add_item(self, item: BaseDataModel) -> None:
        """Add an item to CosmosDB."""
        await self._ensure_initialized()

        try:
            # Convert to dictionary and handle datetime serialization
            document = item.model_dump()

            for key, value in list(document.items()):
                if isinstance(value, datetime.datetime):
                    document[key] = value.isoformat()

            await self.container.create_item(body=document)
        except Exception as e:
            self.logger.error("Failed to add item to CosmosDB: %s", str(e))
            raise

    async def update_item(self, item: BaseDataModel) -> None:
        """Update an item in CosmosDB."""
        await self._ensure_initialized()

        try:
            # Convert to dictionary and handle datetime serialization
            document = item.model_dump()
            for key, value in list(document.items()):
                if isinstance(value, datetime.datetime):
                    document[key] = value.isoformat()
            await self.container.upsert_item(body=document)
        except Exception as e:
            self.logger.error("Failed to update item in CosmosDB: %s", str(e))
            raise

    async def get_item_by_id(
        self, item_id: str, partition_key: str, model_class: Type[BaseDataModel]
    ) -> Optional[BaseDataModel]:
        """Retrieve an item by its ID and partition key."""
        await self._ensure_initialized()

        try:
            item = await self.container.read_item(
                item=item_id, partition_key=partition_key
            )
            return model_class.model_validate(item)
        except Exception as e:
            self.logger.error("Failed to retrieve item from CosmosDB: %s", str(e))
            return None

    async def query_items(
        self,
        query: str,
        parameters: List[Dict[str, Any]],
        model_class: Type[BaseDataModel],
    ) -> List[BaseDataModel]:
        """Query items from CosmosDB and return a list of model instances."""
        await self._ensure_initialized()

        try:
            items = self.container.query_items(query=query, parameters=parameters)
            result_list = []
            async for item in items:
                # item["ts"] = item["_ts"]
                try:
                    result_list.append(model_class.model_validate(item))
                except Exception as validation_error:
                    self.logger.warning(
                        "Failed to validate item: %s", str(validation_error)
                    )
                    continue
            return result_list
        except Exception as e:
            self.logger.error("Failed to query items from CosmosDB: %s", str(e))
            return []

    async def delete_item(self, item_id: str, partition_key: str) -> None:
        """Delete an item from CosmosDB."""
        await self._ensure_initialized()

        try:
            await self.container.delete_item(item=item_id, partition_key=partition_key)
        except Exception as e:
            self.logger.error("Failed to delete item from CosmosDB: %s", str(e))
            raise

    # Plan Operations
    async def add_plan(self, plan: Plan) -> None:
        """Add a plan to CosmosDB."""
        await self.add_item(plan)

    async def update_plan(self, plan: Plan) -> None:
        """Update a plan in CosmosDB."""
        await self.update_item(plan)

    async def get_plan_by_plan_id(self, plan_id: str) -> Optional[Plan]:
        """Retrieve a plan by plan_id."""
        query = "SELECT * FROM c WHERE c.id=@plan_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@user_id", "value": self.user_id},
        ]
        results = await self.query_items(query, parameters, Plan)
        return results[0] if results else None

    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Retrieve a plan by plan_id."""
        return await self.get_plan_by_plan_id(plan_id)

    async def get_all_plans(self) -> List[Plan]:
        """Retrieve all plans for the user."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
            {"name": "@data_type", "value": DataType.plan},
        ]
        return await self.query_items(query, parameters, Plan)

    async def get_all_plans_by_team_id(self, team_id: str) -> List[Plan]:
        """Retrieve all plans for a specific team, newest first.

        Every status. This is the chat list's read (#74): filtering it to
        ``completed`` hid five of the six statuses from the panel, and the chat
        most worth resuming is the one that did not finish. The ordering is
        the panel's row order and is why the ``ORDER BY`` is here rather than
        only on the status-filtered query it replaced.
        """
        query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type and c.user_id=@user_id ORDER BY c._ts DESC"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
            {"name": "@team_id", "value": team_id},
            {"name": "@data_type", "value": DataType.plan},
        ]
        return await self.query_items(query, parameters, Plan)

    async def get_plan_by_session(
        self, session_id: str, plan_id: Optional[str] = None
    ) -> Optional[Plan]:
        """The Plan record **Ending a turn** settles (#120, ADR-031).

        Without ``plan_id``, the Chat's **latest** Plan: a Chat's state is its
        latest Plan's (#71) and every turn mints a new one, so the newest is the
        only one an end-of-turn may write. With one — the turn registry knows
        exactly which Plan the turn it just cancelled was answering — that plan
        within that session, because "the session's latest" stops being the
        cancelled turn's record the moment a newer turn starts.

        Read **raw**, and that is the whole reason this method exists rather
        than another ``query_items`` caller. That helper maps *every* failure to
        an empty list, so a Cosmos outage arrives indistinguishable from a
        session holding no plan — and this caller ends an orchestration on the
        strength of the answer. Reported as no chat, an outage would kill the
        turn and then write nothing, leaving the **Abandoned turn** this
        primitive exists to end. It also drops a document it cannot validate,
        which would promote an *older* settled plan to "the chat's state" and
        write `canceled` onto a turn that finished long ago. Both are refused
        the same way `delete_chat` refuses them: raw, and ``TOP 1`` so there is
        no older row to fall back to.

        Scoped by ``user_id``, which is the whole of the authorization for the
        reason :meth:`delete_chat` records: a session id is not a secret, and
        ``process_request`` takes one from the caller.
        """
        await self._ensure_initialized()

        named = " AND c.id=@plan_id" if plan_id is not None else ""
        parameters = [
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@user_id", "value": self.user_id},
        ]
        if plan_id is not None:
            parameters.append({"name": "@plan_id", "value": plan_id})

        rows = self.container.query_items(
            query=(
                "SELECT TOP 1 * FROM c "
                "WHERE c.session_id=@session_id AND c.data_type=@data_type "
                f"AND c.user_id=@user_id{named} ORDER BY c._ts DESC"
            ),
            parameters=parameters,
        )

        async for row in rows:
            return Plan.model_validate(row)

        return None

    async def get_all_plans_by_team_id_status(
        self, user_id: str, team_id: str, status: str
    ) -> List[Plan]:
        """Retrieve all plans for a specific team."""
        query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type and c.user_id=@user_id and c.overall_status=@status ORDER BY c._ts DESC"
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@team_id", "value": team_id},
            {"name": "@data_type", "value": DataType.plan},
            {"name": "@status", "value": status},
        ]
        return await self.query_items(query, parameters, Plan)

    # Step Operations
    async def add_step(self, step: Step) -> None:
        """Add a step to CosmosDB."""
        await self.add_item(step)

    async def update_step(self, step: Step) -> None:
        """Update a step in CosmosDB."""
        await self.update_item(step)

    async def get_steps_by_plan(self, plan_id: str) -> List[Step]:
        """Retrieve all steps for a plan."""
        query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type ORDER BY c.timestamp"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": DataType.step},
        ]
        return await self.query_items(query, parameters, Step)

    async def get_step(self, step_id: str, session_id: str) -> Optional[Step]:
        """Retrieve a step by step_id and session_id."""
        query = "SELECT * FROM c WHERE c.id=@step_id AND c.session_id=@session_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@step_id", "value": step_id},
            {"name": "@session_id", "value": session_id},
            {"name": "@data_type", "value": DataType.step},
        ]
        results = await self.query_items(query, parameters, Step)
        return results[0] if results else None

    # Removed duplicate update_team method definition

    async def get_team(self, team_id: str) -> Optional[TeamConfiguration]:
        """Retrieve a specific team configuration by team_id.

        Ordered newest-first, and that is load-bearing rather than tidy (#54).
        A team marked ``is_default`` cannot be deleted — `delete_team` refuses —
        so the post-provision re-upload that is meant to *replace* it warns and
        uploads anyway, writing a second document with the same ``team_id``
        under a **new partition key**. Both are then live, and an unordered
        `teams[0]` returns whichever Cosmos hands back first.

        Every re-upload adds another. The symptom is a configuration change that
        works on one deployment, silently does nothing on the next, and cannot
        be reproduced from the repository: the store team's
        ``require_all_agents`` flag would be read off a document written before
        the flag existed and default to True, putting the walkthrough's opening
        beat back through three specialists.

        Args:
            team_id: The team_id of the team configuration to retrieve

        Returns:
            TeamConfiguration object or None if not found
        """
        query = (
            "SELECT * FROM c WHERE c.team_id=@team_id "
            "AND c.data_type=@data_type "
            "AND (c.user_id=@user_id OR c.is_default=true) "
            "ORDER BY c._ts DESC"
        )
        parameters = [
            {"name": "@team_id", "value": team_id},
            {"name": "@data_type", "value": DataType.team_config},
            {"name": "@user_id", "value": self.user_id},
        ]
        teams = await self.query_items(query, parameters, TeamConfiguration)
        return teams[0] if teams else None

    async def get_team_by_id(self, team_id: str) -> Optional[TeamConfiguration]:
        """Retrieve a specific team configuration by its document id.

        Args:
            id: The document id of the team configuration to retrieve

        Returns:
            TeamConfiguration object or None if not found
        """
        query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type AND (c.user_id=@user_id OR c.is_default=true)"
        parameters = [
            {"name": "@team_id", "value": team_id},
            {"name": "@data_type", "value": DataType.team_config},
            {"name": "@user_id", "value": self.user_id},
        ]
        teams = await self.query_items(query, parameters, TeamConfiguration)
        return teams[0] if teams else None

    async def get_all_teams(self) -> List[TeamConfiguration]:
        """Retrieve all team configurations visible to the current user.

        Returns:
            List of TeamConfiguration objects: default teams plus user-specific teams
        """
        query = "SELECT * FROM c WHERE c.data_type=@data_type AND (c.user_id=@user_id OR c.is_default=true) ORDER BY c.created DESC"
        parameters = [
            {"name": "@data_type", "value": DataType.team_config},
            {"name": "@user_id", "value": self.user_id},
        ]
        teams = await self.query_items(query, parameters, TeamConfiguration)
        return teams

    async def delete_team(self, team_id: str) -> bool:
        """Delete a team configuration by team_id.

        Only user-owned teams can be deleted; default teams cannot be deleted.

        Args:
            team_id: The team_id of the team configuration to delete

        Returns:
            True if team was found and deleted, False otherwise
        """
        await self._ensure_initialized()

        try:
            # First find the team to get its document id and partition key
            team = await self.get_team(team_id)
            if not team:
                return False
            # Prevent deletion of default teams
            if team.is_default:
                return False
            await self.delete_item(item_id=team.id, partition_key=team.session_id)
            return True
        except Exception as e:
            logging.exception(f"Failed to delete team from Cosmos DB: {e}")
            return False

    # Data Management Operations
    async def get_data_by_type(self, data_type: str) -> List[BaseDataModel]:
        """Retrieve all data of a specific type."""
        query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        parameters = [
            {"name": "@data_type", "value": data_type},
            {"name": "@user_id", "value": self.user_id},
        ]

        # Get the appropriate model class
        model_class = self.MODEL_CLASS_MAPPING.get(data_type, BaseDataModel)
        return await self.query_items(query, parameters, model_class)

    async def get_all_items(self) -> List[Dict[str, Any]]:
        """Retrieve all items as dictionaries."""
        query = "SELECT * FROM c WHERE c.user_id=@user_id"
        parameters = [
            {"name": "@user_id", "value": self.user_id},
        ]

        await self._ensure_initialized()
        items = self.container.query_items(query=query, parameters=parameters)
        results = []
        async for item in items:
            results.append(item)
        return results

    # Collection Management (for compatibility)

    # Additional compatibility methods
    async def get_steps_for_plan(self, plan_id: str) -> List[Step]:
        """Alias for get_steps_by_plan for compatibility."""
        return await self.get_steps_by_plan(plan_id)

    async def add_team(self, team: TeamConfiguration) -> None:
        """Add a team configuration to Cosmos DB.

        Args:
            team: The TeamConfiguration to add
        """
        await self.add_item(team)

    async def update_team(self, team: TeamConfiguration) -> None:
        """Update an existing team configuration in Cosmos DB.

        Args:
            team: The TeamConfiguration to update
        """
        await self.update_item(team)

    async def get_current_team(self, user_id: str) -> Optional[UserCurrentTeam]:
        """Retrieve the current team for a user."""
        await self._ensure_initialized()
        if self.container is None:
            return None

        query = "SELECT * FROM c WHERE c.data_type=@data_type AND c.user_id=@user_id"
        parameters = [
            {"name": "@data_type", "value": DataType.user_current_team},
            {"name": "@user_id", "value": user_id},
        ]

        # Get the appropriate model class
        teams = await self.query_items(query, parameters, UserCurrentTeam)
        return teams[0] if teams else None

    async def delete_current_team(self, user_id: str) -> bool:
        """Delete the current team for a user."""
        query = "SELECT c.id, c.session_id FROM c WHERE c.user_id=@user_id AND c.data_type=@data_type"

        params = [
            {"name": "@user_id", "value": user_id},
            {"name": "@data_type", "value": DataType.user_current_team},
        ]
        items = self.container.query_items(query=query, parameters=params)
        self.logger.debug("delete_current_team: querying items for user_id=%s", user_id)
        if items:
            async for doc in items:
                try:
                    await self.container.delete_item(
                        doc["id"], partition_key=doc["session_id"]
                    )
                except Exception as e:
                    self.logger.warning(
                        "Failed deleting current team doc %s: %s", doc.get("id"), e
                    )

        return True

    async def set_current_team(self, current_team: UserCurrentTeam) -> None:
        """Set the current team for a user."""
        await self._ensure_initialized()
        await self.add_item(current_team)

    async def update_current_team(self, current_team: UserCurrentTeam) -> None:
        """Update the current team for a user."""
        await self._ensure_initialized()
        await self.update_item(current_team)

    async def delete_plan_by_plan_id(self, plan_id: str) -> bool:
        """Delete a plan by its ID.

        **Not Chat deletion** (ADR-026). It takes one plan document, carries no
        ``user_id`` predicate and returns ``True`` whatever happened, so
        routing it as the surface's delete control would leave the transcript
        and the session-scoped records behind and let a caller who knows an id
        reach another user's chat. It keeps its single caller — the
        human-feedback rejection path — and ``delete_chat`` is the operation
        the panel is wired to.
        """
        query = "SELECT c.id, c.session_id FROM c WHERE c.id=@plan_id "

        params = [
            {"name": "@plan_id", "value": plan_id},
        ]
        items = self.container.query_items(query=query, parameters=params)
        self.logger.debug("delete_plan_by_plan_id: querying items for plan_id=%s", plan_id)
        if items:
            async for doc in items:
                try:
                    await self.container.delete_item(
                        doc["id"], partition_key=doc["session_id"]
                    )
                except Exception as e:
                    self.logger.warning(
                        "Failed deleting current team doc %s: %s", doc.get("id"), e
                    )

        return True

    async def delete_chat(self, session_id: str) -> ChatDeletion:
        """**Chat deletion** — every document in one Chat's session partition.

        #75 / ADR-026. A Chat is a Session (ADR-025) and everything the
        conversation produced is written into that session's partition: its
        plans, their steps, the transcript, ``m_plan``, the **Troubleshooting
        record**, the **Simulated ticket** and the **Session state**. Deleting
        the plan alone would leave the conversation behind under a control that
        promised to remove it, so the sweep is the partition's and is
        deliberately not narrowed by ``data_type``.

        Two things stand between a session id and that sweep, and both are
        here rather than at the route, so no second caller can forget them:

        * **Ownership.** The Chat is read back by its session *and* this
          client's ``user_id``, and then the partition itself is checked for a
          record belonging to somebody else before anything is deleted.
          Nothing else authorizes the delete — a session id is not a secret,
          and ``process_request`` takes one from the caller.
        * **A running Chat is kept.** The state is the chat's **latest** plan's
          (#71), which the newest-first read puts first, and ``is_running`` is
          fail-closed about statuses it does not know.

        Both reads go to the container directly rather than through
        ``query_items``, which is a decision and not a shortcut: that helper
        drops documents it cannot validate into a model and turns a Cosmos
        failure into an empty list. Here either would defeat the rule above —
        an unreadable newest plan would promote an older settled one, and an
        outage would report a live chat as no chat at all.

        **A Chat is a live thing while this runs**, and that is the third
        guard. The status check, the enumeration and the deletes are separate
        operations, and ``process_request`` can write a new Plan into the
        session between any two of them — so "the chat was settled when we
        looked" is not the sentence ADR-026 makes. Three things close that,
        and the last of them is an admission rather than a fix:

        * The status is read **again** after the partition has been
          enumerated. A latest plan the enumeration never saw is a turn that
          started behind it, and the chat is running now.
        * The latest plan is deleted **first**, conditionally on the ``_etag``
          that read observed. A plan that moved refuses the delete, and
          because nothing else has been touched yet the chat is kept whole
          rather than left half-swept.
        * The partition is **counted afterwards**. A record written behind the
          sweep cannot be prevented by either guard, so it is reported: the
          chat comes back ``incomplete``, never ``deleted``.

        Two residues are left, both known and neither closeable without a
        deletion fence every session writer honours — its own ticket:

        * A document written after that final count is indistinguishable, from
          here, from one written after this method returned. The chat *was*
          deleted; what follows is a new record in a session id somebody still
          holds.
        * A sweep that takes the latest plan and then fails on a later document
          leaves a partition the chat list cannot show, because the list is
          built from plans. It is reported ``incomplete`` and logged, and the
          surface deliberately does not tell the associate to retry from a row
          that is no longer there.

        Reports what actually happened. A sweep that could not take every
        document comes back ``incomplete``, because a half-deleted chat is
        still in Cosmos.
        """
        await self._ensure_initialized()

        # Newest first: a Chat's state is its latest plan's, and this read is
        # also the first half of the ownership check — a session that yields no
        # plan of this user's is, to this caller, no chat at all.
        status, _plan_id, _etag, found = await self._latest_plan(session_id)

        if not found:
            return ChatDeletion(DeletionOutcome.no_such_chat)

        if is_running(status):
            return ChatDeletion(DeletionOutcome.still_running)

        # The partition is enumerated in full before a single delete. Owning
        # one plan in a session does not make the session's every document
        # yours, and discovering that halfway through the sweep would leave a
        # chat neither deleted nor intact.
        documents = self.container.query_items(
            query="SELECT c.id, c.user_id FROM c WHERE c.session_id=@session_id",
            parameters=[{"name": "@session_id", "value": session_id}],
        )

        doomed = []
        async for doc in documents:
            owner = doc.get("user_id")
            # `None` is not somebody else. The Session state, the
            # Troubleshooting record and the Simulated ticket are written
            # against the session rather than against a user.
            if owner is not None and owner != self.user_id:
                self.logger.warning(
                    "Refusing to delete session %s: it holds another user's record",
                    session_id,
                )
                return ChatDeletion(DeletionOutcome.not_yours)
            doomed.append(doc["id"])

        # Read the state again, now that the sweep knows exactly which
        # documents it would take. Everything this second read can disagree
        # with the first about is a turn that started while the partition was
        # being read, and every disagreement keeps the chat.
        status, plan_id, etag, found = await self._latest_plan(session_id)

        if not found:
            return ChatDeletion(DeletionOutcome.no_such_chat)

        if is_running(status) or plan_id not in doomed or not etag:
            if plan_id not in doomed:
                self.logger.info(
                    "Keeping chat %s: plan %s was written after its partition "
                    "was read",
                    session_id,
                    plan_id,
                )
            return ChatDeletion(DeletionOutcome.still_running)

        deleted = 0
        failed = 0

        # The latest plan goes first, and only if it is still the document that
        # was read. A refusal here costs nothing — no other document has been
        # touched — which is the whole reason it is not swept in list order.
        try:
            await self.container.delete_item(
                plan_id,
                partition_key=session_id,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
            deleted += 1
        except Exception as e:
            if getattr(e, "status_code", None) == PRECONDITION_FAILED:
                self.logger.info(
                    "Keeping chat %s: its latest plan changed under the sweep",
                    session_id,
                )
                return ChatDeletion(DeletionOutcome.still_running)
            failed += 1
            self.logger.warning("Failed deleting chat document %s: %s", plan_id, e)

        for document_id in doomed:
            if document_id == plan_id:
                continue
            try:
                await self.container.delete_item(
                    document_id, partition_key=session_id
                )
                deleted += 1
            except Exception as e:
                failed += 1
                self.logger.warning(
                    "Failed deleting chat document %s: %s", document_id, e
                )

        if not failed:
            # Nothing refused the sweep, so the only thing that can still be in
            # this partition is something written into it while the sweep ran.
            # A chat with a record left in it is not a deleted chat.
            left_behind = await self._count_partition(session_id)
            if left_behind:
                self.logger.warning(
                    "Chat %s gained %s document(s) while it was being deleted",
                    session_id,
                    left_behind,
                )
                failed = left_behind

        return ChatDeletion.swept(deleted=deleted, failed=failed)

    async def _latest_plan(self, session_id: str):
        """The Chat's latest Plan, read raw: status, id, ``_etag``, found.

        Raw for the reason ``delete_chat`` documents — ``query_items`` would
        drop a plan it cannot validate and turn an outage into an empty
        history — and it carries the ``_etag`` because the sweep's first delete
        is conditional on it.
        """
        rows = self.container.query_items(
            query=(
                "SELECT TOP 1 c.overall_status, c.id, c._etag FROM c "
                "WHERE c.session_id=@session_id AND c.data_type=@data_type "
                "AND c.user_id=@user_id ORDER BY c._ts DESC"
            ),
            parameters=[
                {"name": "@session_id", "value": session_id},
                {"name": "@data_type", "value": DataType.plan},
                {"name": "@user_id", "value": self.user_id},
            ],
        )

        async for row in rows:
            return row.get("overall_status"), row.get("id"), row.get("_etag"), True

        return None, None, None, False

    async def _count_partition(self, session_id: str) -> int:
        """How many documents are left in a Chat's partition."""
        rows = self.container.query_items(
            query="SELECT VALUE COUNT(1) FROM c WHERE c.session_id=@session_id",
            parameters=[{"name": "@session_id", "value": session_id}],
        )

        async for count in rows:
            return int(count or 0)

        return 0

    async def delete_all_chats(self, team_id: str) -> ChatsDeletion:
        """**Chat deletion** applied to the whole list (#76, ADR-026).

        A presenter clearing the stage between rehearsal runs, in one action.
        Every chat that goes is handed to :meth:`delete_chat` and goes on
        exactly its terms — the whole session partition, scoped to this
        ``user_id``, and a running chat kept by the same fail-closed rule. That
        method is not re-implemented here on purpose: it is where ownership is
        proved twice and where the partition is read in full before anything is
        deleted, and a second copy would be a second place to forget all of it.

        The enumeration is this method's own decision, and it is **not** the
        panel's list handed back: sweeping whatever the browser named would let
        one associate clear another's history. It does have to *be* that list,
        though, and by review it was not — the chat list is read by **team**
        (``get_all_plans_by_team_id``) and the confirmation states that list's
        count, so an enumeration scoped only by ``user_id`` would destroy chats
        the dialog never mentioned. The two reads therefore ask the same
        question of the store, in the same two predicates, and the ``team_id``
        arrives from the caller's *current team* rather than from the request.

        Deduped in Python rather than by ``DISTINCT``: a Chat holds more than
        one Plan (#71) — the walkthrough's centrepiece pair is one chat with
        two — and sweeping the same partition twice reports the second pass as
        ``no_such_chat``, which would put a phantom failure in front of the
        presenter.

        A store failure while enumerating is raised rather than read as an
        empty history: "there was nothing to delete" and "the list could not be
        read" are the same sentence to a panel, and the first one lets the
        surface report a history that is sitting untouched in Cosmos as gone.

        One chat that will not go does not stop the others. Stopping at the
        first failure leaves the list half-cleared with no account of where it
        stopped, which is worse than the failure; the result says which chats
        went instead.
        """
        await self._ensure_initialized()

        sessions = self.container.query_items(
            query=(
                "SELECT c.session_id FROM c "
                "WHERE c.user_id=@user_id AND c.team_id=@team_id "
                "AND c.data_type=@data_type"
            ),
            parameters=[
                {"name": "@user_id", "value": self.user_id},
                {"name": "@team_id", "value": team_id},
                {"name": "@data_type", "value": DataType.plan},
            ],
        )

        # Order-preserving, so the sweep runs in the order the store answered
        # and a re-read of the log follows it.
        doomed: List[str] = []
        async for row in sessions:
            session_id = row.get("session_id")
            if session_id and session_id not in doomed:
                doomed.append(session_id)

        results = []
        for session_id in doomed:
            try:
                results.append((session_id, await self.delete_chat(session_id)))
            except Exception as e:
                self.logger.warning("Failed deleting chat %s: %s", session_id, e)
                results.append((session_id, ChatDeletion(DeletionOutcome.incomplete)))

        return ChatsDeletion.tally(results)

    async def add_mplan(self, mplan: MPlan) -> None:
        """Add a team configuration to the database."""
        await self.add_item(mplan)

    async def update_mplan(self, mplan: MPlan) -> None:
        """Update a team configuration in the database."""
        await self.update_item(mplan)

    async def get_mplan(self, plan_id: str) -> Optional[MPlan]:
        """Retrieve a mplan configuration by mplan_id."""
        query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": DataType.m_plan},
        ]
        results = await self.query_items(query, parameters, MPlan)
        return results[0] if results else None

    async def add_agent_message(self, message: AgentMessageData) -> None:
        """Add an agent message to the database."""
        await self.add_item(message)

    async def update_agent_message(self, message: AgentMessageData) -> None:
        """Update an agent message in the database."""
        await self.update_item(message)

    async def get_agent_messages(self, plan_id: str) -> List[AgentMessageData]:
        """Retrieve an agent message by message_id."""
        query = "SELECT * FROM c WHERE c.plan_id=@plan_id AND c.data_type=@data_type ORDER BY c._ts ASC"
        parameters = [
            {"name": "@plan_id", "value": plan_id},
            {"name": "@data_type", "value": DataType.m_plan_message},
        ]

        return await self.query_items(query, parameters, AgentMessageData)

    async def add_team_agent(self, team_agent: CurrentTeamAgent) -> None:
        """Add an agent message to the database."""
        await self.delete_team_agent(team_agent.team_id, team_agent.agent_name)  # Ensure no duplicates
        await self.add_item(team_agent)

    async def delete_team_agent(self, team_id: str, agent_name: str) -> None:
        """Delete the current team for a user."""
        query = "SELECT c.id, c.session_id FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type AND c.agent_name=@agent_name"

        params = [
            {"name": "@team_id", "value": team_id},
            {"name": "@agent_name", "value": agent_name},
            {"name": "@data_type", "value": DataType.current_team_agent},
        ]
        items = self.container.query_items(query=query, parameters=params)
        self.logger.debug("delete_team_agent: querying items for team_id=%s agent_name=%s", team_id, agent_name)
        if items:
            async for doc in items:
                try:
                    await self.container.delete_item(
                        doc["id"], partition_key=doc["session_id"]
                    )
                except Exception as e:
                    self.logger.warning(
                        "Failed deleting current team doc %s: %s", doc.get("id"), e
                    )

        return True

    async def get_team_agent(
        self, team_id: str, agent_name: str
    ) -> Optional[CurrentTeamAgent]:
        """Retrieve a team agent by team_id and agent_name."""
        query = "SELECT * FROM c WHERE c.team_id=@team_id AND c.data_type=@data_type AND c.agent_name=@agent_name"
        params = [
            {"name": "@team_id", "value": team_id},
            {"name": "@agent_name", "value": agent_name},
            {"name": "@data_type", "value": DataType.current_team_agent},
        ]

        results = await self.query_items(query, params, CurrentTeamAgent)
        return results[0] if results else None
