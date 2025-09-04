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
    MagenticContext, StandardMagenticManager)
from semantic_kernel.agents.orchestration.prompts._magentic_prompts import \
    ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT
from semantic_kernel.contents import ChatMessageContent
from v3.config.settings import (connection_config, current_user_id,
                                orchestration_config)
from v3.models.models import MPlan, MStep


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

        custom_addition = """
Before creating the final plan, please ask each agent - team member to list all relevant tools (including MCP tools, plug-ins, etc.) they have access to.  For each tool, list its required parameters.
Obtain every required parameter that is not specified in the users request. These questions should be sent to the proxy agent.  Do not ask for information that is outside of this list of required parameters.

Once this information is obtained, replan to create a final bullet-point plan to address the original request using the data and clarifications obtained.
Each step in the plan should start with a specific agent which is responsible for executing it.
"""

        kwargs['task_ledger_plan_prompt'] = ORCHESTRATOR_TASK_LEDGER_PLAN_PROMPT + custom_addition
        
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
        
        # Send the approval request to the user's WebSocket
        # The user_id will be automatically retrieved from context
        await connection_config.send_status_update_async({
            "type": "plan_approval_request", 
            "data": approval_message
        })
        
        # Wait for user approval
        approval_response = await self._wait_for_user_approval(approval_message.plan.id)
        
        if approval_response and approval_response.approved:
            print("Plan approved - proceeding with execution...")
            return plan
        else:
            print("Plan execution cancelled by user")
            await connection_config.send_status_update_async({
                "type": "plan_approval_response", 
                "data": approval_response
            })
            raise Exception("Plan execution cancelled by user") 
            # return ChatMessageContent(
            #     role="assistant",
            #     content="Plan execution was cancelled by the user."
            # )
            
    
    async def _wait_for_user_approval(self, plan_dot_id: Optional[str] = None) -> Optional[messages.PlanApprovalResponse]: # plan_id will not be optional in future
        """Wait for user approval response."""
        
        # To do: implement timeout and error handling
        if plan_dot_id not in orchestration_config.approvals:
            orchestration_config.approvals[plan_dot_id] = None
        while orchestration_config.approvals[plan_dot_id] is None:
            await asyncio.sleep(0.2)
        return messages.PlanApprovalResponse(approved=orchestration_config.approvals[plan_dot_id], plan_dot_id=plan_dot_id)

    
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
        """
        """
        
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


