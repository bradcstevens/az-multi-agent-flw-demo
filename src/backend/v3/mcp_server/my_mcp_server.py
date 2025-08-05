from fastmcp import FastMCP
from fastmcp.server.auth import BearerAuthProvider
from utils.utils_date import format_date_for_user

from enum import Enum


auth = BearerAuthProvider(
    jwks_uri="https://login.microsoftonline.com/52b39610-0746-4c25-a83d-d4f89fadedfe/discovery/v2.0/keys",
    #issuer="https://login.microsoftonline.com/52b39610-0746-4c25-a83d-d4f89fadedfe/v2.0",
    # This issuer is not correct in the docs. Found by decoding the token.
    issuer="https://sts.windows.net/52b39610-0746-4c25-a83d-d4f89fadedfe/",
    algorithm="RS256",
    audience="api://7a95e70b-062e-4cd3-a88c-603fc70e1c73"
)

class Domain(Enum):
    HR = "hr"
    MARKETING = "marketing" 
    PROCUREMENT = "procurement"
    PRODUCT = "product"
    TECH_SUPPORT = "tech_support"
    RETAIL = "Retail"

mcp = FastMCP("My MCP Server", auth=auth)

formatting_instructions = "Instructions: returning the output of this function call verbatim to the user in markdown. Then write AGENT SUMMARY: and then include a summary of what you did."

@mcp.tool
def greet(name: str) -> str:
    """    Greets the user with the provided name."""
    return f"Hello from MCP, {name}!"

@mcp.tool(tags={Domain.HR.value})
async def schedule_orientation_session(employee_name: str, date: str) -> str:
    """Schedule an orientation session for a new employee."""
    formatted_date = format_date_for_user(date)

    return (
        f"##### Orientation Session Scheduled\n"
        f"**Employee Name:** {employee_name}\n"
        f"**Date:** {formatted_date}\n\n"
        f"Your orientation session has been successfully scheduled. "
        f"Please mark your calendar and be prepared for an informative session.\n"
        f"AGENT SUMMARY: I scheduled the orientation session for {employee_name} on {formatted_date}, as part of her onboarding process.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.HR.value})
async def assign_mentor(employee_name: str) -> str:
    """Assign a mentor to a new employee."""
    return (
        f"##### Mentor Assigned\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"A mentor has been assigned to you. They will guide you through your onboarding process and help you settle into your new role.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.HR.value})
async def register_for_benefits(employee_name: str) -> str:
    """Register a new employee for benefits."""
    return (
        f"##### Benefits Registration\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"You have been successfully registered for benefits. "
        f"Please review your benefits package and reach out if you have any questions.\n"
        f"{formatting_instructions}"
    )
    
@mcp.tool(tags={Domain.HR.value})
async def provide_employee_handbook(employee_name: str) -> str:
    """Provide the employee handbook to a new employee."""
    return (
        f"##### Employee Handbook Provided\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"The employee handbook has been provided to you. "
        f"Please review it to familiarize yourself with company policies and procedures.\n"
        f"{formatting_instructions}"
    )
    
@mcp.tool(tags={Domain.HR.value})
async def initiate_background_check(employee_name: str) -> str:
    """Initiate a background check for a new employee."""
    return (
        f"##### Background Check Initiated\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"A background check has been initiated for {employee_name}. "
        f"You will be notified once the check is complete.\n"
        f"{formatting_instructions}"
    )
    
@mcp.tool(tags={Domain.HR.value})
async def request_id_card(employee_name: str) -> str:
    """Request an ID card for a new employee."""
    return (
        f"##### ID Card Request\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"Your request for an ID card has been successfully submitted. "
        f"Please allow 3-5 business days for processing. You will be notified once your ID card is ready for pickup.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.HR.value})
async def set_up_payroll(employee_name: str) -> str:
    """Set up payroll for a new employee."""
    return (
        f"##### Payroll Setup\n"
        f"**Employee Name:** {employee_name}\n\n"
        f"Your payroll has been successfully set up. "
        f"Please review your payroll details and ensure everything is correct.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.TECH_SUPPORT.value})
async def send_welcome_email(employee_name: str, email_address: str) -> str:
    """Send a welcome email to a new employee as part of onboarding."""
    return (
        f"##### Welcome Email Sent\n"
        f"**Employee Name:** {employee_name}\n"
        f"**Email Address:** {email_address}\n\n"
        f"A welcome email has been successfully sent to {employee_name} at {email_address}.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.TECH_SUPPORT.value})
async def set_up_office_365_account(employee_name: str, email_address: str) -> str:
    """Set up an Office 365 account for an employee."""
    return (
        f"##### Office 365 Account Setup\n"
        f"**Employee Name:** {employee_name}\n"
        f"**Email Address:** {email_address}\n\n"
        f"An Office 365 account has been successfully set up for {employee_name} at {email_address}.\n"
        f"{formatting_instructions}"
    )

@mcp.tool(tags={Domain.TECH_SUPPORT.value})
async def configure_laptop(employee_name: str, laptop_model: str) -> str:
    """Configure a laptop for a new employee."""
    return (
        f"##### Laptop Configuration\n"
        f"**Employee Name:** {employee_name}\n"
        f"**Laptop Model:** {laptop_model}\n\n"
        f"The laptop {laptop_model} has been successfully configured for {employee_name}.\n"
        f"{formatting_instructions}"
    )

if __name__ == "__main__":
    mcp.run()

# Start as http server: fastmcp run my_mcp_server.py -t streamable-http -l DEBUG