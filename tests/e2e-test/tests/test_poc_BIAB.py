import logging

from config.constants import prompt_question1, prompt_question2, rai_prompt, employee_details, product_details
from pages.BIAB import BIABPage

logger = logging.getLogger(__name__)


def test_biab_PAGE_AUTOMATION(login_logout):
    """Validate Golden path test case for Multi-Agent-Custom-Automation-Engine"""
    page = login_logout
    biab_page = BIABPage(page)
    logger.info("Step 1: Validate home page is loaded.")
    biab_page.validate_home_page()
    logger.info("Step 2: Validate Run Sample prompt1 & run plans")
    biab_page.enter_a_question(prompt_question1)
    biab_page.click_send_button()
    biab_page.click_my_task()
    biab_page.enter_aditional_info(employee_details)
    # biab_page.click_aditional_send_button()
    biab_page.processing_different_stage()
    biab_page.click_new_task()
    logger.info("Step 3: Validate Run Sample prompt2 & run plans")
    biab_page.enter_a_question(prompt_question2)
    biab_page.click_send_button()
    biab_page.click_my_task()
    biab_page.enter_aditional_info(product_details)
    # biab_page.click_aditional_send_button()
    biab_page.processing_different_stage()
    biab_page.click_new_task()
    logger.info("Step 4: Validate Run Sample prompt3 from Quick Tasks & run plans")
    biab_page.click_mobile_plan()
    biab_page.click_send_button()
    biab_page.click_my_task()
    biab_page.processing_different_stage()
    biab_page.click_new_task()
    logger.info(
        "Step 5: Validate Run known RAI test prompts to ensure that you get the toast saying that a plan cannot be generated"
    )
    biab_page.enter_a_question(rai_prompt)
    biab_page.validate_rai_validation_message()
