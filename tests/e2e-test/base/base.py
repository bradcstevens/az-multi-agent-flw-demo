from config.constants import API_URL
from dotenv import load_dotenv


class BasePage:
    def __init__(self, page):
        self.page = page

    def scroll_into_view(self, locator):
        reference_list = locator
        locator.nth(reference_list.count() - 1).scroll_into_view_if_needed()

    def is_visible(self, locator):
        locator.is_visible()

    def validate_response_status(self):

        load_dotenv()

        # The URL of the API endpoint you want to access
        api_url = f"{API_URL}/api/plans"

        headers = {
            "Accept": "*/*",
        }

        # Make the GET request
        response = self.page.request.get(api_url, headers=headers, timeout=120000)

        # Check the response status code with custom error message
        try:
            assert response.status == 200
        except AssertionError:
            raise AssertionError(
                f"Expected response code 200, but got {response.status}. Response body: {response.text()}"
            )
