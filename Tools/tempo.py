import json
import time
import aiohttp
import logging
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException
from dataclasses import dataclass
import asyncio

# Constants
CONFIG_PATH = './CredentialSettings.json'
MAX_RETRIES = 4
WAIT_TIME = 3
PAGE_LOAD_TIMEOUT = 30

# Configuration
class Config:
    JIRA_URL = "jira.xxx.yyy"
    DEFAULT_USER = "jira_user_name"
    DEFAULT_PASSWORD = "jira_pwd"
    BASE_URL = f"https://{JIRA_URL}"
    LOGIN_PATH = "/login.jsp"
    TEMPO_API_PATH = "/rest/tempo-timesheets/4/worklogs/"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CookieSet:
    name: str
    value: str

class CookieSetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, CookieSet):
            return {'name': obj.name, 'value': obj.value}
        return super().default(obj)

@dataclass
class CredentialSettings:
    user: str = Config.DEFAULT_USER
    pwd: str = Config.DEFAULT_PASSWORD
    JSESSIONID: Optional[CookieSet] = None
    AtlassianXsrfToken: Optional[CookieSet] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'CredentialSettings':
        settings = cls(
            user=data.get('user', Config.DEFAULT_USER),
            pwd=data.get('pwd', Config.DEFAULT_PASSWORD)
        )
        if cookie_data := data.get('JSESSIONID'):
            settings.JSESSIONID = CookieSet(**cookie_data)
        if token_data := data.get('AtlassianXsrfToken'):
            settings.AtlassianXsrfToken = CookieSet(**token_data)
        return settings

class CookieService:
    def __init__(self, credential_settings: CredentialSettings):
        self.credential_settings = credential_settings

    def _get_web_driver(self) -> WebDriver:
        options = Options()
        options.page_load_strategy = 'normal'
        options.add_argument('--disable-crash-reporter')
        options.add_argument('--disable-logging')
        options.add_argument('--log-level=3')
        options.add_argument('--output=/dev/null')
        
        return webdriver.Chrome(service=Service(), options=options)

    async def _save_cookies(self, cookies: List[dict]) -> None:
        for cookie in cookies:
            name = cookie['name'].lower()
            if name == "jsessionid":
                self.credential_settings.JSESSIONID = CookieSet(name=cookie['name'], value=cookie['value'])
            elif name in ("atl.xsrf.token", "atlassian.xsrf.token"):
                self.credential_settings.AtlassianXsrfToken = CookieSet(name=cookie['name'], value=cookie['value'])

        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.credential_settings.__dict__, f, cls=CookieSetEncoder)
        except IOError as e:
            logger.error(f"Failed to save cookies: {e}")
            raise

    def _handle_login_form(self, driver: WebDriver) -> None:
        try:
            username_field = driver.find_element(By.ID, "login-form-username")
            password_field = driver.find_element(By.ID, "login-form-password")
            
            username_field.clear()
            password_field.clear()
            
            username_field.send_keys(self.credential_settings.user)
            password_field.send_keys(self.credential_settings.pwd)
        except WebDriverException as e:
            logger.error(f"Failed to fill login form: {e}")
            raise

    def _click_element_with_retry(self, driver: WebDriver, element_id: str) -> None:
        for attempt in range(MAX_RETRIES):
            try:
                element = driver.find_element(By.ID, element_id)
                if element.is_displayed():
                    element.click()
                    return
            except WebDriverException as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to click element {element_id}: {e}")
                    raise
                time.sleep(WAIT_TIME)

    async def get_jira_cookies(self) -> None:
        driver = None

        try:
            driver = self._get_web_driver()
            wait = WebDriverWait(driver, PAGE_LOAD_TIMEOUT)
            
            driver.get(f"{Config.BASE_URL}{Config.LOGIN_PATH}")
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            
            time.sleep(WAIT_TIME)
            self._click_element_with_retry(driver, "login-form-submit")
            self._handle_login_form(driver)
            self._click_element_with_retry(driver, "login-form-submit")
            
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            time.sleep(WAIT_TIME)
            
            cookies = driver.get_cookies()
            if not cookies:
                raise ValueError("No cookies obtained")
            
            await self._save_cookies(cookies)
            logger.info("Successfully obtained and saved cookies")
            
        except Exception as e:
            logger.error(f"Error during cookie retrieval: {e}")
            raise
        finally:
            if driver:
                driver.quit()

    async def post_tempo_worklog(self, tempo_data: Dict[str, Any]) -> bool:
        try:
            with open(CONFIG_PATH, 'r') as f:
                saved_settings = CredentialSettings.from_dict(json.load(f))
        except IOError as e:
            logger.error(f"Failed to read credentials: {e}")
            return False

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/118.0.0.0',
            'Origin': Config.BASE_URL,
            'Content-Type': 'application/json'
        }

        cookies = {
            saved_settings.AtlassianXsrfToken.name: saved_settings.AtlassianXsrfToken.value,
            saved_settings.JSESSIONID.name: saved_settings.JSESSIONID.value
        }

        try:
            async with aiohttp.ClientSession(cookies=cookies) as session:
                async with session.post(
                    f"{Config.BASE_URL}{Config.TEMPO_API_PATH}",
                    json=tempo_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info("Tempo worklog posted successfully")
                        return True
                    else:
                        logger.error(f"Failed to post tempo worklog: {response.status}")
                        return False
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            return False

# Example usage remains the same
if __name__ == "__main__":
    async def main():
        cookie_service = CookieService(CredentialSettings())
        await cookie_service.get_jira_cookies()
        
        # Example tempo data
        tempo_data = {
            "attributes":{},
            "billableSeconds": None,
            "originId":-1,
            "worker":"JIRAUSER15",
            "comment":None,
            "started":"2025-01-21",
            "timeSpentSeconds":3600,
            "originTaskId":"42",
            "remainingEstimate":0,
            "endDate":None,
            "includeNonWorkingDays":None
        }
        
        await cookie_service.post_tempo_worklog(tempo_data)

    asyncio.run(main())