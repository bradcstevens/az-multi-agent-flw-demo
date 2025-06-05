from base.base import BasePage
from playwright.sync_api import expect


class BIABPage(BasePage):
    WELCOME_PAGE_TITLE = (
        "//span[normalize-space()='Multi-Agent-Custom-Automation-Engine']"
    )
    NEW_TASK_PROMPT = "//textarea[@id='newTaskPrompt']"
    SEND_BUTTON = "//button[@class='send-button']"
    TASK_LIST = "//span[contains(text(),'1.')]"
    NEW_TASK = "//button[@id='newTaskButton']"
    MOBILE_PLAN = "//div[@class='columns']//div[1]//div[1]//div[1]"
    MOBILE_TASK1 = "//span[contains(text(),'1.')]"
    MOBILE_TASK2 = "//span[contains(text(),'2.')]"
    MOBILE_APPROVE_TASK1 = "i[title='Approve']"
    ADDITIONAL_INFO = "//textarea[@id='taskMessageTextarea']"
    ADDITIONAL_INFO_SEND_BUTTON = "//button[@id='taskMessageAddButton']"
    STAGES = "//i[@title='Approve']"

    def __init__(self, page):
        super().__init__(page)
        self.page = page

    def click_my_task(self):
        # self.page.locator(self.TASK_LIST).click()
        # self.page.wait_for_timeout(2000)
        self.page.locator(self.TASK_LIST).click()
        self.page.wait_for_timeout(10000)

    def enter_aditional_info(self, text):
        additional_info = self.page.frame("viewIframe").locator(self.ADDITIONAL_INFO)

        if (additional_info).is_enabled():
            additional_info.fill(text)
            self.page.wait_for_timeout(5000)
            # Click on send button in question area
            self.page.frame("viewIframe").locator(
                self.ADDITIONAL_INFO_SEND_BUTTON
            ).click()
            self.page.wait_for_timeout(5000)

    def click_send_button(self):
        # Click on send button in question area
        self.page.frame("viewIframe").locator(self.SEND_BUTTON).click()
        self.page.wait_for_timeout(25000)
        # self.page.wait_for_load_state('networkidle')

    def validate_rai_validation_message(self):
        # Click on send button in question area
        self.page.frame("viewIframe").locator(self.SEND_BUTTON).click()
        self.page.wait_for_timeout(1000)
        expect(
            self.page.frame("viewIframe").locator("//div[@class='notyf-announcer']")
        ).to_have_text("Unable to create plan for this task.")
        self.page.wait_for_timeout(3000)

    def click_aditional_send_button(self):
        # Click on send button in question area
        self.page.frame("viewIframe").locator(self.ADDITIONAL_INFO_SEND_BUTTON).click()
        self.page.wait_for_timeout(5000)

    def click_new_task(self):
        self.page.locator(self.NEW_TASK).click()
        self.page.wait_for_timeout(5000)

    def click_mobile_plan(self):
        self.page.frame("viewIframe").locator(self.MOBILE_PLAN).click()
        self.page.wait_for_timeout(3000)

    def validate_home_page(self):
        expect(self.page.locator(self.WELCOME_PAGE_TITLE)).to_be_visible()

    def enter_a_question(self, text):
        # Type a question in the text area
        # self.page.pause()
        self.page.frame("viewIframe").locator(self.NEW_TASK_PROMPT).fill(text)
        self.page.wait_for_timeout(5000)

    def processing_different_stage(self):
        if self.page.frame("viewIframe").locator(self.STAGES).count() >= 1:
            for i in range(self.page.frame("viewIframe").locator(self.STAGES).count()):
                approve_stages = (
                    self.page.frame("viewIframe").locator(self.STAGES).nth(0)
                )
                approve_stages.click()
                self.page.wait_for_timeout(10000)
                BasePage.validate_response_status(self)
                self.page.wait_for_timeout(10000)
        expect(
            self.page.frame("viewIframe").locator("//tag[@id='taskStatusTag']")
        ).to_have_text("Completed")
        expect(
            self.page.frame("viewIframe").locator("//div[@id='taskProgressPercentage']")
        ).to_have_text("100%")
