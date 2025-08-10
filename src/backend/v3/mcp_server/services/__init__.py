"""
Services module for MCP server.
"""

from .hr_service import HRService
from .tech_support_service import TechSupportService
from .general_service import GeneralService

__all__ = ["HRService", "TechSupportService", "GeneralService"]
