"""
Human-in-the-loop Magentic Manager for employee onboarding orchestration.
Extends StandardMagenticManager to add approval gates before plan execution.
"""

import asyncio
import re
from typing import Any, List, Optional

import v3.models.messages as messages
from semantic_kernel.agents import Agent
from semantic_kernel.agents.orchestration.magentic import (
    MagenticContext, ProgressLedger, ProgressLedgerItem,
    StandardMagenticManager)
from semantic_kernel.agents.orchestration.prompts._magentic_prompts import (
    ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT)
from semantic_kernel.contents import ChatMessageContent
from v3.config.settings import (connection_config, current_user_id,
                                orchestration_config)
from v3.models.models import MPlan, MStep

            # Create a progress ledger that indicates the request is satisfied (task complete)


class HumanApprovalMagenticManager(StandardMagenticManager):
    """
    Extended Magentic manager that requires human approval before executing plan steps.
    Provides interactive approval for each step in the orchestration plan.
    """
    
    # Define Pydantic fields to avoid validation errors
    approval_enabled: bool = True
    magentic_plan: Optional[MPlan] = None
    current_user_id: Optional[str] = None 

    def __init__(self, *args, **kwargs):
        # Remove any custom kwargs before passing to parent

        # Use object.__setattr__ to bypass Pydantic validation
        # object.__setattr__(self, 'current_user_id', None)

        facts_append = """

        """

        plan_append = """
IMPORTANT: Never ask the user for information or clarification until all agents on the team have been asked first.

EXAMPLE: If the user request involves product information, first ask all agents on the team to provide the information. 
Do not ask the user unless all agents have been consulted and the information is still missing.

Plan steps should always include a bullet point, followed by an agent name, followed by a description of the action
to be taken. If a step involves multiple actions, separate them into distinct steps with an agent included in each step. If the step is taken by an agent that 
is not part of the team, such as the MagenticManager, please always list the MagenticManager as the agent for that step. At any time, if more information is 
needed from the user, use the ProxyAgent to request this information.

Here is an example of a well-structured plan:
- **EnhancedResearchAgent** to gather authoritative data on the latest industry trends and best practices in employee onboarding
- **EnhancedResearchAgent** to gather authoritative data on Innovative onboarding techniques that enhance new hire engagement and retention.
- **DocumentCreationAgent** to draft a comprehensive onboarding plan that includes a detailed schedule of onboarding activities and milestones.
- **DocumentCreationAgent** to draft a comprehensive onboarding plan that includes a checklist of resources and materials needed for effective onboarding.
- **ProxyAgent** to review the drafted onboarding plan for clarity and completeness.
- **MagenticManager** to finalize the onboarding plan and prepare it for presentation to stakeholders.

"""

        # kwargs["task_ledger_facts_prompt"] = ORCHESTRATOR_TASK_LEDGER_FACTS_PROMPT + facts_append
        kwargs['task_ledger_plan_prompt'] = ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT + plan_append
        kwargs['task_ledger_plan_update_prompt'] = ORCHESTRATOR_TASK_LEDGER_PLAN_UPDATE_PROMPT + plan_append
        
        super().__init__(*args, **kwargs)

    async def plan(self, magentic_context: MagenticContext) -> Any:
        """
        Override the plan method to create the plan first, then ask for approval before execution.
        """
        # Extract task text from the context
        task_text = magentic_context.task
        if hasattr(task_text, 'content'):
            task_text = task_text.content
        elif not isinstance(task_text, str):
            task_text = str(task_text)
        
        print(f"\n Human-in-the-Loop Magentic Manager Creating Plan:")
        print(f"   Task: {task_text}")
        print("-" * 60)
        
        # First, let the parent create the actual plan
        print(" Creating execution plan...")
        plan = await super().plan(magentic_context)
        print(f" Plan created: {plan}")
        self.magentic_plan = self.plan_to_obj( magentic_context, self.task_ledger)

        self.magentic_plan.user_id = current_user_id.get()

        # Request approval from the user before executing the plan
        approval_message = messages.PlanApprovalRequest(
            plan=self.magentic_plan,
            status="PENDING_APPROVAL",
            context={
                "task": task_text,
                "participant_descriptions": magentic_context.participant_descriptions
            } if hasattr(magentic_context, 'participant_descriptions') else {}
        )
        try:
            orchestration_config.plans[self.magentic_plan.id] = self.magentic_plan 
        except Exception as e:
            print(f"Error processing plan approval: {e}")


        # Send the approval request to the user's WebSocket
        # The user_id will be automatically retrieved from context
        await connection_config.send_status_update_async(
            message=approval_message,
            user_id=current_user_id.get(),
            message_type=messages.WebsocketMessageType.PLAN_APPROVAL_REQUEST)
        
        # Wait for user approval
        approval_response = await self._wait_for_user_approval(approval_message.plan.id)
        
        if approval_response and approval_response.approved:
            print("Plan approved - proceeding with execution...")
            return plan
        else:
            print("Plan execution cancelled by user")
            await connection_config.send_status_update_async({
                "type": messages.WebsocketMessageType.PLAN_APPROVAL_RESPONSE, 
                "data": approval_response
            }, user_id=current_user_id.get(), message_type=messages.WebsocketMessageType.PLAN_APPROVAL_RESPONSE)
            raise Exception("Plan execution cancelled by user") 
            
    async def replan(self,magentic_context: MagenticContext) -> Any:
        """ 
        Override to add websocket messages for replanning events. 
        """

        print(f"\nHuman-in-the-Loop Magentic Manager replanned:")
        replan = await super().replan(magentic_context=magentic_context)
        print("Replanned: %s", replan)
        return replan
    
    async def create_progress_ledger(self, magentic_context: MagenticContext) -> ProgressLedger:
        """ Check for max rounds exceeded and send final message if so. """
        if magentic_context.round_count >= orchestration_config.max_rounds:
            # Send final message to user
            final_message = messages.FinalResultMessage(
                content="Process terminated: Maximum rounds exceeded",
                status="terminated",
                summary=f"Stopped after {magentic_context.round_count} rounds (max: {orchestration_config.max_rounds})"
            )
            
            await connection_config.send_status_update_async(
                message= final_message,
                user_id=current_user_id.get(),
                message_type=messages.WebsocketMessageType.FINAL_RESULT_MESSAGE)
            
            return ProgressLedger(
                is_request_satisfied=ProgressLedgerItem(reason="Maximum rounds exceeded", answer=True),
                is_in_loop=ProgressLedgerItem(reason="Terminating", answer=False),
                is_progress_being_made=ProgressLedgerItem(reason="Terminating", answer=False),
                next_speaker=ProgressLedgerItem(reason="Task complete", answer=""),
                instruction_or_question=ProgressLedgerItem(reason="Task complete", answer="Process terminated due to maximum rounds exceeded")
            )
        
        return await super().create_progress_ledger(magentic_context)
    
    async def _wait_for_user_approval(self, m_plan_id: Optional[str] = None) -> Optional[messages.PlanApprovalResponse]: # plan_id will not be optional in future
        """Wait for user approval response."""
        
        # To do: implement timeout and error handling
        if m_plan_id not in orchestration_config.approvals:
            orchestration_config.approvals[m_plan_id] = None
        while orchestration_config.approvals[m_plan_id] is None:
            await asyncio.sleep(0.2)
        return messages.PlanApprovalResponse(approved=orchestration_config.approvals[m_plan_id], m_plan_id=m_plan_id)

    async def prepare_final_answer(self, magentic_context: MagenticContext) -> ChatMessageContent:
        """
        Override to ensure final answer is prepared after all steps are executed.
        """
        print("\n Magentic Manager - Preparing final answer...")

        return await super().prepare_final_answer(magentic_context)

    
    async def _get_plan_approval_with_details(self, task: str, participant_descriptions: dict, plan: Any) -> bool:
        while True:
            approval = input("\ Approve this execution plan? [y/n/details]: ").strip().lower()
            
            if approval in ['y', 'yes']:
                print(" Plan approved by user")
                return True
            elif approval in ['n', 'no']:
                print(" Plan rejected by user")
                return False
            # elif approval in ['d', 'details']:
            #     self._show_detailed_plan_info(task, participant_descriptions, plan)
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'details' for more info")
    

    def plan_to_obj(self, magentic_context, ledger) -> MPlan:
        """ Convert the generated plan from the ledger into a structured MPlan object. """
        
        return_plan: MPlan = MPlan()

        # get the request text from the ledger
        if hasattr(magentic_context, 'task'):
            return_plan.user_request = magentic_context.task

        return_plan.team = list(magentic_context.participant_descriptions.keys())
        
        # Get the facts content from the ledger
        if hasattr(ledger, 'facts') and ledger.facts.content:
            return_plan.facts = ledger.facts.content

        # Get the plan / steps content from the ledger
        # Split the description into lines and clean them
        lines = [line.strip() for line in ledger.plan.content.strip().split('\n') if line.strip()]
        
        found_agent = None
        prefix = None
        
        for line in lines:
            # match lines that look like bullet points
            if re.match(r'^[-•*]\s+', line):
                # Remove the bullet point marker
                line = re.sub(r'^[-•*]\s+', '', line).strip()
            
            # Look for agent names in the line
            
            for agent_name in return_plan.team:
                # Check if agent name appears in the line (case insensitive)
                if agent_name.lower() in line.lower():
                    found_agent = agent_name
                    line = line.split(agent_name, 1)
                    line = line[1].strip() if len(line) > 1 else ""
                    line = line.replace('*', '').strip()
                    break
            
            if not found_agent:
                # If no agent found, assign to ProxyAgent if available
                found_agent = "MagenticAgent"
            # If line indicates a following list of actions (e.g. "Assign **EnhancedResearchAgent** 
            # to gather authoritative data on:") save and prefix to the steps
            if line.endswith(':'):
                line = line.replace(':', '').strip()
                prefix = line + " "

            # Don't create a step if action is blank 
            if line.strip() != "":
                if prefix:
                    line = prefix + line
                # Create the step object
                step = MStep(agent=found_agent, action=line)

                # add the step to the plan
                return_plan.steps.append(step) # pylint: disable=E1101

        return return_plan


