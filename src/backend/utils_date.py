import locale
from datetime import datetime
import logging
from typing import Optional

from app_config import config

# Try to import babel, with fallback if not available
try:
    from babel.dates import format_datetime
    BABEL_AVAILABLE = True
except ImportError:
    BABEL_AVAILABLE = False
    logging.warning("Babel library not available. Date formatting will use basic Python formatting.")


def _format_date_fallback(date_obj: datetime, language_code: str) -> str:
    """
    Fallback date formatting when babel is not available.
    
    Args:
        date_obj (datetime): The datetime object to format
        language_code (str): Language code like 'en-US', 'en-IN', etc.
    
    Returns:
        str: Formatted date string
    """
    # Normalize the language code
    normalized_code = language_code.replace('-', '_')
    
    # Define basic date formats for different locales
    locale_date_formats = {
        'en_IN': '%d %B, %Y',      # 29 July, 2025
        'en_US': '%B %d, %Y',      # July 29, 2025
        'en_GB': '%d %B %Y',       # 29 July 2025
        'en_AU': '%d %B %Y',       # 29 July 2025
        'en_CA': '%B %d, %Y',      # July 29, 2025
        'es_ES': '%d de %B de %Y', # Would need Spanish month names
        'fr_FR': '%d %B %Y',       # Would need French month names
        'de_DE': '%d. %B %Y',      # Would need German month names
        'ja_JP': '%Y年%m月%d日',    # 2025年07月29日
        'ko_KR': '%Y년 %m월 %d일', # 2025년 07월 29일
        'zh_CN': '%Y年%m月%d日',    # 2025年07月29日
    }
    
    # Get the format for the locale, default to US format
    date_format = locale_date_formats.get(normalized_code, '%B %d, %Y')
    
    try:
        return date_obj.strftime(date_format)
    except Exception as e:
        logging.warning("Fallback date formatting failed: %s", str(e))
        return date_obj.strftime('%Y-%m-%d')  # ISO format as last resort


def format_date_for_user(date_str: str, user_locale: Optional[str] = None) -> str:
    """
    Format date based on user's desktop locale preference.

    Args:
        date_str (str): Date in ISO format (YYYY-MM-DD) or datetime object.
        user_locale (str, optional): User's locale string, e.g., 'en_US', 'en_GB'.

    Returns:
        str: Formatted date respecting locale or raw date if formatting fails.
    """
    try:
        # Get user's browser language from config
        lang = config.get_user_local_browser_language()  # e.g., 'en-US', 'fr-FR', 'de-DE'
        
        # Parse the date string if it's a string, otherwise use as-is if it's already a datetime
        if isinstance(date_str, str):
            # Try different date formats
            date_formats = [
                "%Y-%m-%d",           # 2025-07-29
                "%Y-%m-%d",  # 2025-07-29 14:30:00
                "%Y-%m-%d",  # 2025-07-29T14:30:00
                "%d/%m/%Y",           # 29/07/2025
                "%m/%d/%Y",           # 07/29/2025
            ]
            
            parsed_date = None
            for date_format in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, date_format)
                    break
                except ValueError:
                    continue
            
            if parsed_date is None:
                logging.warning("Could not parse date string: %s", date_str)
                return date_str  # Return original string if parsing fails
            
            date_to_format = parsed_date
        else:
            # Assume it's already a datetime object
            date_to_format = date_str
        
        # Format the date using babel with the user's locale, or fallback to basic formatting
        if BABEL_AVAILABLE:
            try:
                # Babel expects locale in format like 'en_US', not 'en-US'
                babel_locale = lang.replace('-', '_')
                formatted_date = format_datetime(date_to_format, locale=babel_locale)
            except Exception as e:
                logging.warning("Babel formatting failed: %s. Using fallback formatting.", str(e))
                formatted_date = _format_date_fallback(date_to_format, lang)
        else:
            formatted_date = _format_date_fallback(date_to_format, lang)
        
        print(
            f"Formatted date for user ######################### : {formatted_date} using locale: {lang},browser lang {config.get_user_local_browser_language()}, locale: {babel_locale}"
        )
        return formatted_date
        
    except Exception as e:
        logging.error("Error formatting date '%s': %s", date_str, str(e))
        # Return the original input if anything goes wrong
        return str(date_str)