"""
Veterans Verify - Browser Automation Core
Using Camoufox for best anti-detection

Complete Workflow:
1. Create temporary email
2. Register/Login ChatGPT (Email verification code)
3. Enter SheerID Veterans verification form
4. Fill veteran info (Real BIRLS data + Random discharge date)
5. Submit form, wait for email verification link
6. Click link to complete verification
"""
import os
import re
import time
import random
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from camoufox.async_api import AsyncNewBrowser
import logging

logger = logging.getLogger(__name__)


class VerifyStatus(Enum):
    """Verification Status"""
    PENDING = "pending"
    CREATING_EMAIL = "creating_email"
    REGISTERING_CHATGPT = "registering_chatgpt"
    WAITING_CHATGPT_CODE = "waiting_chatgpt_code"
    CONFIRMING_AGE = "confirming_age"  # New: Confirm age page
    OPENING_SHEERID = "opening_sheerid"
    FILLING_FORM = "filling_form"
    SUBMITTING = "submitting"
    WAITING_VERIFY_LINK = "waiting_verify_link"
    CLICKING_LINK = "clicking_link"
    CHECKING_RESULT = "checking_result"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class VerifyTask:
    """Verification Task"""
    task_id: str
    status: VerifyStatus = VerifyStatus.PENDING
    email: Optional[str] = None
    password: str = ""
    first_name: str = ""
    last_name: str = ""
    branch: str = ""
    birth_date: Dict[str, str] = field(default_factory=dict)
    discharge_date: Dict[str, str] = field(default_factory=dict)
    screenshots: list = field(default_factory=list)
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class HumanBehavior:
    """Human Behavior Simulation"""

    def __init__(self, delay_min: int = 50, delay_max: int = 150):
        self.delay_min = delay_min
        self.delay_max = delay_max

    def random_delay(self, base: float = 1.0, variance: float = 0.5) -> float:
        """Generate normal distribution random delay"""
        delay = random.gauss(base, variance)
        return max(0.1, delay)

    def typing_delay(self) -> float:
        """Typing delay (ms to s)"""
        return random.randint(self.delay_min, self.delay_max) / 1000

    @staticmethod
    def generate_random_birthday(min_age: int = 20, max_age: int = 25) -> Dict[str, str]:
        """
        Generate random birthday (for confirm age page)

        Args:
            min_age: Min age (default 20)
            max_age: Max age (default 25)

        Returns:
            {"year": "2002", "month": "3", "day": "15"}
        """
        today = datetime.now()
        age = random.randint(min_age, max_age)
        birth_year = today.year - age
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)  # Avoid month day issues

        return {
            "year": str(birth_year),
            "month": str(birth_month),
            "day": str(birth_day)
        }

    @staticmethod
    def generate_random_name() -> str:
        """Generate random English name (for confirm age page)"""
        first_names = [
            "James", "John", "Michael", "David", "Chris", "Daniel", "Matthew", "Andrew",
            "Emily", "Sarah", "Jessica", "Ashley", "Amanda", "Jennifer", "Elizabeth", "Rachel"
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson",
            "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee", "Harris"
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"


class BrowserWorker:
    """Browser Automation Worker"""

    # URLs
    VETERANS_CLAIM_URL = "https://chatgpt.com/veterans-claim"
    SHEERID_URL = "https://services.sheerid.com/verify/690415d58971e73ca187d8c9/"

    # Form Options
    BRANCH_OPTIONS = [
        "Air Force", "Army", "Coast Guard",
        "Marine Corps", "Navy", "Space Force"
    ]

    def __init__(self, headless: bool = True, screenshot_dir: str = ""):
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        # from veteran_data import VeteranDataManager  # Delayed import
        self.human = HumanBehavior()

    # ==================== Manual Verification Helpers ====================

    async def run_manual_token_verify(self, task: VerifyTask, verify_url: str, proxy: Optional[str] = None) -> bool:
        """Manual Token Verification with Proxy and Verbose Logging"""
        try:
            # 1. Init Browser (with proxy if provided)
            logger.info(f"[Task {task.task_id}] Initializing browser with proxy: {proxy}")
            if not await self.init_browser(proxy=proxy):
                logger.error(f"[Task {task.task_id}] Browser Info Failed")
                return False

            # 2. Open URL
            logger.info(f"[Task {task.task_id}] Opening verification URL: {verify_url}")
            await self.page.goto(verify_url, timeout=60000)
            await asyncio.sleep(2.0)

            # 3. Detect Button
            logger.info(f"[Task {task.task_id}] Looking for 'Verify Email' button...")
            # Common selectors for ChatGPT/Auth0 verification
            button_selectors = [
                'a:has-text("Verify email address")',
                'button:has-text("Verify email address")', 
                'a[href*="verify-email"]',
                '[data-testid="verify-email-button"]',
                'text=Verify your email' # Fallback text match
            ]
            
            verify_btn = None
            for selector in button_selectors:
                try:
                    verify_btn = await self.page.query_selector(selector)
                    if verify_btn:
                        logger.info(f"[Task {task.task_id}] Found button with selector: {selector}")
                        break
                except:
                    continue
            
            if verify_btn:
                # 4. Click Button
                logger.info(f"[Task {task.task_id}] Clicking 'Verify Email' button...")
                await verify_btn.click()
                await asyncio.sleep(5.0) # Wait for result
                
                # Check for success
                content = await self.page.content()
                if "success" in content.lower() or "verified" in content.lower():
                     logger.info(f"[Task {task.task_id}] Verification successful (Content match)")
                     return True
                else:
                     logger.warning(f"[Task {task.task_id}] Clicked button but success message not found immediately.")
                     return True # Assume success if clicked without error? Or take screenshot
            else:
                # Maybe it auto-verified?
                logger.info(f"[Task {task.task_id}] No button found. Checking page content for auto-verification...")
                content = await self.page.content()
                if "verified" in content.lower() or "success" in content.lower():
                     logger.info(f"[Task {task.task_id}] Auto-verification detected.")
                     return True
                
                logger.error(f"[Task {task.task_id}] Failed to find verify button or success message.")
                await self.take_screenshot(task, "error_token_verify_failed", force=True)
                return False
                
        except Exception as e:
            logger.error(f"[Task {task.task_id}] Token verify exception: {e}")
            await self.take_screenshot(task, "error_token_exception", force=True)
            return False
        finally:
            await self.close_browser()
    async def init_browser(self, proxy: Optional[str] = None):
        """Initialize browser"""
        if self.page:
            return True

        try:
            from playwright.async_api import async_playwright
            logger.info("[Browser] Starting Playwright...")
            self.playwright = await async_playwright().start()
            
            # Proxy Config
            launch_args = {
                "headless": self.headless,
                "geoip": True,
                "locale": "en-US",
                "humanize": True,
                "timeout": 60000, # Increased timeout for slow proxies
            }
            if proxy:
                logger.info(f"[Browser] Using Proxy: {proxy}")
                launch_args["proxy"] = {"server": proxy}

            logger.info("[Browser] Initializing Camoufox...")
            self.browser = await AsyncNewBrowser(self.playwright, **launch_args)

            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            logger.info("[Browser] Camoufox initialized successfully")
            return True
        except Exception as e:
            logger.error(f"[Browser] Initialization failed: {e}")
            return False

    async def close_browser(self):
        """Close Browser"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
        except Exception as e:
            logger.error(f"[Browser] Close failed: {e}")

    async def take_screenshot(self, task: VerifyTask, name: str, force: bool = False):
        """Take Screenshot (Optimized: Only on error or forced)"""
        if not self.screenshot_dir:
            return

        # Optimization: Only take screenshot if force=True or task status is FAILED/ERROR
        if not force and task.status not in [VerifyStatus.FAILED, "ERROR", "FAILED"]:
            return

        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            path = os.path.join(self.screenshot_dir, f"{task.task_id}_{name}_{int(time.time())}.png")
            if self.page:
                await self.page.screenshot(path=path)
                logger.debug(f"[Browser] Screenshot saved: {path}")
        except Exception as e:
            logger.error(f"[Browser] Screenshot failed: {e}")

    async def human_type(self, selector: str, text: str, clear_first: bool = True):
        """Human-like Typing"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=10000)
            if element:
                await element.click()
                await asyncio.sleep(self.human.random_delay(0.2, 0.1))

                if clear_first:
                    await self.page.keyboard.press("Control+a")
                    await asyncio.sleep(0.1)

                for char in text:
                    await self.page.keyboard.type(char)
                    await asyncio.sleep(self.human.typing_delay())

                return True
        except Exception as e:
            logger.error(f"[Input] Typing failed {selector}: {e}")
            return False

    async def click_element(self, selector: str, timeout: int = 10000) -> bool:
        """Click Element"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                await asyncio.sleep(self.human.random_delay(0.3, 0.1))
                await element.click()
                return True
        except Exception as e:
            logger.error(f"[Click] Click failed {selector}: {e}")
            return False

    async def select_dropdown(self, trigger_selector: str, option_text: str) -> bool:
        """Select Dropdown Option"""
        try:
            # Click to trigger dropdown
            await self.click_element(trigger_selector)
            await asyncio.sleep(self.human.random_delay(0.5, 0.2))

            # Click option
            option_selector = f'[role="option"]:has-text("{option_text}"), li:has-text("{option_text}"), div[role="listbox"] >> text="{option_text}"'
            await self.click_element(option_selector, timeout=5000)
            await asyncio.sleep(self.human.random_delay(0.3, 0.1))

            return True
        except Exception as e:
            logger.error(f"[Dropdown] Selection failed {option_text}: {e}")
            return False

    # ==================== Confirm Age Page ====================

    async def handle_about_you_page(self, task: VerifyTask) -> bool:
        """
        Handle Confirm Age Page (auth.openai.com/about-you)

        This page appears after new user registration, requires:
        1. Full Name (Randomly generated)
        2. Birthday (Between 20-25 years old)
        """
        current_url = self.page.url
        if "about-you" not in current_url:
            return True  # Not on this page, skip

        task.status = VerifyStatus.CONFIRMING_AGE
        logger.info(f"[Task {task.task_id}] Processing Confirm Age page")

        try:
            await asyncio.sleep(self.human.random_delay(1.0, 0.3))

            # Generate random info (20-25 years old)
            random_name = self.human.generate_random_name()
            random_birthday = self.human.generate_random_birthday(min_age=20, max_age=25)

            logger.debug(f"[Task {task.task_id}] Random Name: {random_name}, Birthday: {random_birthday}")

            # 1. Fill Full Name
            name_input = await self.page.wait_for_selector('input[name="name"]', timeout=10000)
            if name_input:
                await self.human_type('input[name="name"]', random_name)
                await asyncio.sleep(self.human.random_delay(0.5, 0.2))
                
                # Press Tab to move to birthday field (more reliable than clicking)
                logger.info(f"[Task {task.task_id}] Pressing Tab to navigate to birthday field...")
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(0.5)

            # 2. Fill Birthday
            # The page uses React Aria DateField with spinbutton divs (not regular inputs)
            logger.info(f"[Task {task.task_id}] Filling birthday fields...")
            
            try:
                # Type MM/DD/YYYY directly using keyboard since we tabbed into the date field group
                # We rely on React Aria's AUTO-ADVANCE feature.
                # Evidence showed that adding ArrowRight/Tab caused skipping (Double Jump).
                
                # Type Month (2 digits) -> Should auto-advance to Day
                await self.page.keyboard.type(random_birthday["month"].zfill(2))
                await asyncio.sleep(0.5) # Wait for auto-advance
                logger.info(f"[Task {task.task_id}] Filled month: {random_birthday['month']}")

                # Type Day (2 digits) -> Should auto-advance to Year
                await self.page.keyboard.type(random_birthday["day"].zfill(2))
                await asyncio.sleep(0.5) # Wait for auto-advance
                logger.info(f"[Task {task.task_id}] Filled day: {random_birthday['day']}")

                # Type Year (4 digits)
                await self.page.keyboard.type(random_birthday["year"])
                await asyncio.sleep(0.5)
                logger.info(f"[Task {task.task_id}] Filled year: {random_birthday['year']}")
                    
            except Exception as e:
                logger.warning(f"[Task {task.task_id}] Birthday filling error: {e}")

            await self.take_screenshot(task, "04b_about_you_filled")

            # 3. Click Continue button
            logger.info(f"[Task {task.task_id}] Clicking Continue...")
            # Use specific selector or enter key
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(1.0)
            
            continue_btn = await self.page.query_selector('button[type="submit"]')
            if continue_btn:
                try:
                    await continue_btn.click()
                except:
                    pass # Maybe enter key worked
            
            # CRITICAL: Wait for login to complete and redirect to finish
            logger.info(f"[Task {task.task_id}] Waiting for login finalization...")
            await asyncio.sleep(10.0) # Give enough time for auth cookies to set
            
            await self.take_screenshot(task, "04c_after_about_you")
            logger.info(f"[Task {task.task_id}] Confirm Age page completed and submitted")
            return True

        except Exception as e:
            logger.error(f"[Task {task.task_id}] Confirm Age page failed: {e}")
            task.error_message = f"Confirm Age page failed: {e}"
            task.error_type = "ABOUT_YOU_ERROR"
            await self.take_screenshot(task, "error_about_you")
            return False

    # ==================== ChatGPT Registration Flow ====================

    async def register_chatgpt(self, task: VerifyTask, email_manager) -> bool:
        """
        Register ChatGPT Account

        Flow:
        1. Open veterans-claim page
        2. Click Login
        3. Enter Email
        4. Create Password
        5. Enter Email Verification Code
        """
        task.status = VerifyStatus.REGISTERING_CHATGPT

        try:
            # 1. Open Veterans Claim Page
            logger.info(f"[Task {task.task_id}] Open Veterans Claim Page")
            await self.page.goto(self.VETERANS_CLAIM_URL)
            await asyncio.sleep(self.human.random_delay(3.0, 1.0))
            await self.take_screenshot(task, "01_veterans_claim")

            # 2. Click Login Button
            login_btn = await self.page.query_selector('button:has-text("Log in"), button:has-text("Sign in"), button:has-text("Masuk")')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(self.human.random_delay(3.0, 1.0))
            await self.take_screenshot(task, "02_login_page")

            # 2b. Check if on phone login mode and switch to email
            current_url = self.page.url
            if "usernameKind=phone" in current_url or "phone_number" in current_url:
                logger.info(f"[Task {task.task_id}] Phone login mode detected, switching to email")
                email_tab = await self.page.query_selector('button:has-text("Email"), a:has-text("Email"), [data-testid="login-with-email"]')
                if email_tab:
                    await email_tab.click()
                    await asyncio.sleep(self.human.random_delay(1.5, 0.5))
                    await self.take_screenshot(task, "02b_switched_to_email")

            # 3. Enter Email
            email_input = await self.page.wait_for_selector('input[type="email"], input[name="email"], input[autocomplete="email"]', timeout=15000)
            if email_input:
                await self.human_type('input[type="email"], input[name="email"], input[autocomplete="email"]', task.email)
                await asyncio.sleep(self.human.random_delay(0.5, 0.2))

                # Click Continue (Avoid "Continue with Google/Apple/Microsoft/Phone")
                # Prioritize the form submit button, then use text match excluding social logins
                continue_btn = await self.page.query_selector('button[type="submit"]')
                if not continue_btn:
                    # Fallback: match Continue text but exclude all social login buttons
                    continue_btn = await self.page.query_selector('button:has-text("Continue"):not(:has-text("Google")):not(:has-text("Apple")):not(:has-text("Microsoft")):not(:has-text("Phone")):not(:has-text("phone")), button:has-text("Lanjutkan"):not(:has-text("Google")):not(:has-text("Apple")):not(:has-text("Microsoft")):not(:has-text("Phone"))')
                if continue_btn:
                    await continue_btn.click()
                    await asyncio.sleep(self.human.random_delay(3.0, 1.0))

            await self.take_screenshot(task, "03_after_email")

            # Check page status
            page_content = await self.page.content()

            # 4a. If new user, create password
            # Check content first, then URL property
            is_password_page = False
            password_input = await self.page.query_selector('input[type="password"]')
            
            if "Buat kata sandi" in page_content or "Create password" in page_content or "password" in self.page.url or password_input:
                is_password_page = True
                logger.info(f"[Task {task.task_id}] Password page detected")
                
                # If checking via input existence, define detection type
                password_input = await self.page.wait_for_selector('input[type="password"]', timeout=10000)
                if password_input:
                     await self.human_type('input[type="password"]', task.password)
                     # ... rest of logic
                     
                     continue_btn = await self.page.query_selector('button[type="submit"], button:has-text("Lanjutkan"), button:has-text("Continue")')
                     if continue_btn:
                        await continue_btn.click()
                        await asyncio.sleep(self.human.random_delay(3.0, 1.0))

                await self.take_screenshot(task, "04_after_password")

            # 4b. If existing user, enter password (merged logic since input is same)
            # Logic handled above if input[type="password"] is found.
            # But let's keep separate block if text is different and above didn't catch?
            # Actually merging them is safer. Detection of input[type="password"] covers both cases.
            
            # 5. Wait for post-login state OR email verification page
            # This loop handles both: verification code page and successful login
            logger.info(f"[Task {task.task_id}] Waiting for post-login state...")
            login_success = False
            verification_handled = False
            
            for i in range(90):  # Wait up to 90 seconds
                await asyncio.sleep(1.0)
                current_url = self.page.url
                
                if i % 10 == 0:
                    logger.debug(f"[Task {task.task_id}] Wait loop {i}s: {current_url}")
                
                # Case 1: Email verification page detected
                if "email-verification" in current_url and not verification_handled:
                    logger.info(f"[Task {task.task_id}] Email verification page detected")
                    task.status = VerifyStatus.WAITING_CHATGPT_CODE
                    await self.take_screenshot(task, "04b_verification_page")
                    
                    logger.info(f"[Task {task.task_id}] Waiting for ChatGPT verification code...")
                    code = email_manager.check_verification_code(task.email, max_retries=30, interval=3.0)
                    
                    if code:
                        logger.info(f"[Task {task.task_id}] Got verification code: {code}")
                        # Find code input field
                        code_input = await self.page.query_selector('input[name="code"], input[placeholder="Code"], input[type="text"]')
                        if code_input:
                            await code_input.click()
                            await asyncio.sleep(0.2)
                            for char in code:
                                await self.page.keyboard.type(char)
                                await asyncio.sleep(self.human.typing_delay())
                            await asyncio.sleep(self.human.random_delay(0.5, 0.2))
                            
                            # Click Continue
                            continue_btn = await self.page.query_selector('button[type="submit"], button:has-text("Continue")')
                            if continue_btn:
                                await continue_btn.click()
                                await asyncio.sleep(self.human.random_delay(3.0, 1.0))
                        
                        verification_handled = True
                        await self.take_screenshot(task, "04c_after_code")
                        # Continue looping to wait for next page
                    else:
                        task.error_message = "Failed to get ChatGPT verification code"
                        task.error_type = "CHATGPT_CODE_TIMEOUT"
                        return False
                
                # Case 2: About You page
                elif "about-you" in current_url:
                    logger.info(f"[Task {task.task_id}] Detected 'About You' page")
                    if not await self.handle_about_you_page(task):
                        return False
                    login_success = True
                    break
                
                # Case 3: Successfully logged in (ChatGPT main site)
                elif "chatgpt.com" in current_url and "auth" not in current_url and "login" not in current_url:
                    logger.info(f"[Task {task.task_id}] Detected ChatGPT Home/Chat")
                    login_success = True
                    break

            if not login_success:
                 logger.error(f"[Task {task.task_id}] Login timeout. Final URL: {self.page.url}")
                 await self.take_screenshot(task, "error_login_timeout")
                 task.error_message = "Login verification timeout"
                 task.error_type = "LOGIN_TIMEOUT"
                 return False

            # Double check About You just in case
            if "about-you" in self.page.url:
                 if not await self.handle_about_you_page(task):
                    return False

            logger.info(f"[Task {task.task_id}] ChatGPT Login/Register completed")
            return True

        except Exception as e:
            logger.error(f"[Task {task.task_id}] ChatGPT Register Failed: {e}")
            task.error_message = str(e)
            task.error_type = "CHATGPT_REGISTER_ERROR"
            await self.take_screenshot(task, "error_chatgpt")
            return False

    # ==================== SheerID Verification Flow ====================

    async def fill_sheerid_form(self, task: VerifyTask) -> bool:
        """
        Fill SheerID Veterans Verification Form
        """
        task.status = VerifyStatus.FILLING_FORM
        logger.info(f"[Task {task.task_id}] Start filling SheerID form (Specific Selectors)")

        try:
            # Wait for form to load
            await asyncio.sleep(self.human.random_delay(3.0, 1.0))
            await self.take_screenshot(task, "06_sheerid_form")

            # FAST FAIL: Check for "Verification Limit Exceeded"
            limit_exceeded = await self.page.query_selector('text="Verification Limit Exceeded"')
            if limit_exceeded:
                logger.error(f"[Task {task.task_id}] Verification Limit Exceeded detected immediately.")
                task.error_message = "Verification Limit Exceeded"
                task.error_type = "LIMIT_EXCEEDED"
                return False

            # Helper for SheerID custom dropdowns
            async def select_sheerid_dropdown(input_id, menu_id, value):
                try:
                    logger.info(f"Selecting {value} for {input_id}")
                    # Click the input or the button next to it to open menu
                    # Try clicking the expand button specifically if possible
                    expand_btn = await self.page.query_selector(f'#{input_id} + button')
                    if expand_btn:
                        await expand_btn.click()
                    else:
                        await self.page.click(f'#{input_id}')
                    
                    await asyncio.sleep(0.5)
                    
                    # Wait for menu to be visible
                    menu = await self.page.query_selector(f'#{menu_id}')
                    if menu:
                        # Try to find the option by text
                        # SheerID options usually are divs or lis with text
                        option = await self.page.query_selector(f'#{menu_id} div:has-text("{value}"), #{menu_id} li:has-text("{value}")')
                        if option:
                            await option.scroll_into_view_if_needed()
                            await option.click()
                        else:
                            # Fallback: Type partial text in input and hit enter
                            logger.warning(f"Option {value} not found in menu {menu_id}, trying typing...")
                            await self.page.fill(f'#{input_id}', value)
                            await asyncio.sleep(0.5)
                            await self.page.keyboard.press("ArrowDown")
                            await self.page.keyboard.press("Enter")
                    else:
                         # Fallback if menu doesn't appear
                        await self.page.fill(f'#{input_id}', value)
                        await self.page.keyboard.press("Enter")
                        
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error selecting {value} for {input_id}: {e}")

            # 1. Status - "Military Veteran or Retiree" (Not just "Veteran")
            # Note: Value must match exactly what's in the dropdown. 
            # Usually "Veteran" or "Military Veteran". Let's try flexible match if possible, but specific is better.
            await select_sheerid_dropdown("sid-military-status", "sid-military-status-menu", "Military Veteran") 
            # Or "Veterans" - check screenshots if failed. Assuming "Military Veteran" as per common SheerID forms

            # 2. Branch of service
            await select_sheerid_dropdown("sid-branch-of-service", "sid-branch-of-service-menu", task.branch)

            # 3. First name
            logger.debug(f"[Task {task.task_id}] Enter First name: {task.first_name}")
            await self.page.fill('#sid-first-name', task.first_name)
            await asyncio.sleep(0.3)

            # 4. Last name
            logger.debug(f"[Task {task.task_id}] Enter Last name: {task.last_name}")
            await self.page.fill('#sid-last-name', task.last_name)
            await asyncio.sleep(0.3)

            # 5. Date of Birth
            logger.debug(f"[Task {task.task_id}] Fill DOB: {task.birth_date}")
            
            # Month
            # Map numeric month to Name if needed (e.g. "03" -> "March") - task.birth_date["month"] is usually name now?
            # Check create_task: birth_date["month"] is "March". correct.
            await select_sheerid_dropdown("sid-birthdate__month", "sid-birthdate__month-menu", task.birth_date["month"])
            
            # Day
            await self.page.fill('#sid-birthdate-day', task.birth_date["day"])
            await asyncio.sleep(0.2)
            
            # Year
            await self.page.fill('#sid-birthdate-year', task.birth_date["year"])
            await asyncio.sleep(0.2)

            # 6. Discharge Date
            logger.debug(f"[Task {task.task_id}] Fill Discharge: {task.discharge_date}")
            
            # Month
            await select_sheerid_dropdown("sid-discharge-date__month", "sid-discharge-date__month-menu", task.discharge_date["month"])
            
            # Day
            await self.page.fill('#sid-discharge-date-day', task.discharge_date["day"])
            await asyncio.sleep(0.2)
            
            # Year
            await self.page.fill('#sid-discharge-date-year', task.discharge_date["year"])
            await asyncio.sleep(0.2)

            # 7. Email
            logger.debug(f"[Task {task.task_id}] Enter Email: {task.email}")
            await self.page.fill('#sid-email', task.email)
            await asyncio.sleep(0.5)
            
            await self.take_screenshot(task, "07_form_filled")

            # 8. Submit
            logger.info(f"[Task {task.task_id}] Submitting SheerID form...")
            submit_btn = await self.page.query_selector('#sid-submit-btn-collect-info')
            if submit_btn:
                await submit_btn.click()
            else:
                logger.warning("Specific submit button ID not found, trying generic selector")
                await self.page.click('button[type="submit"]')
                
            await asyncio.sleep(self.human.random_delay(5.0, 2.0))
            await self.take_screenshot(task, "08_after_submit")
            
            return True

        except Exception as e:
            logger.error(f"[Task {task.task_id}] SheerID Form Error: {e}")
            await self.take_screenshot(task, "error_sheerid_form")
            return False


    async def submit_and_wait_link(self, task: VerifyTask, email_manager) -> Tuple[bool, str]:
        """
        Submit form and wait for verification link

        Returns: (Success?, Page status or Error message)
        """
        task.status = VerifyStatus.SUBMITTING
        logger.info(f"[Task {task.task_id}] Submitting form")

        try:
            # Click Submit button
            submit_btn = await self.page.query_selector('button:has-text("Verify My Eligibility"), button:has-text("Verify"), button[type="submit"]')
            if submit_btn:
                is_disabled = await submit_btn.get_attribute("disabled")
                if is_disabled:
                    task.error_type = "SUBMIT_DISABLED"
                    return False, "Submit disabled, form might be incomplete"

                await submit_btn.click()
                await asyncio.sleep(self.human.random_delay(3.0, 1.0))

            await self.take_screenshot(task, "08_after_submit")

            # Check page status after submission
            # Retry loop for status detection (wait for page transition)
            status = "unknown"
            for _ in range(10): # Try for 10-15 seconds
                await self.take_screenshot(task, f"waiting_status_{_}")
                page_content = await self.page.content()
                page_url = self.page.url
                status = await self.analyze_page_status(page_content, page_url)
                
                if status != "unknown":
                    break
                
                logger.debug(f"[Task {task.task_id}] Status unknown, URL: {page_url}")
                await asyncio.sleep(1.5)

            logger.info(f"[Task {task.task_id}] Page Status: {status}")

            if status == "need_email_link":
                # Need email verification link
                task.status = VerifyStatus.WAITING_VERIFY_LINK
                logger.info(f"[Task {task.task_id}] Waiting for SheerID verification email link...")

                verify_link = email_manager.check_verification_link(task.email, max_retries=30, interval=3.0)
                if verify_link:
                    logger.info(f"[Task {task.task_id}] Got verification link")
                    task.status = VerifyStatus.CLICKING_LINK

                    # Click link
                    await self.page.goto(verify_link)
                    await asyncio.sleep(self.human.random_delay(3.0, 1.0))
                    await self.take_screenshot(task, "09_after_link")

                    # Check status again
                    final_content = await self.page.content()
                    final_url = self.page.url
                    final_status = await self.analyze_page_status(final_content, final_url)

                    return final_status == "success", final_status
                else:
                    task.error_type = "VERIFY_LINK_TIMEOUT"
                    return False, "Failed to get verification link"

            elif status == "success":
                return True, status

            elif status == "already_verified":
                task.error_type = "ALREADY_VERIFIED"
                return False, "Already verified"

            elif status == "invalid_info":
                task.error_type = "INVALID_INFO"
                return False, "Unable to verify information"

            elif status == "limit_exceeded":
                task.error_type = "LIMIT_EXCEEDED"
                return False, "Verification limit exceeded (already redeemed)"

            else:
                task.error_type = status.upper()
                return False, status

        except Exception as e:
            logger.error(f"[Task {task.task_id}] Submit failed: {e}")
            task.error_type = "SUBMIT_ERROR"
            await self.take_screenshot(task, "error_submit")
            return False, str(e)

    async def analyze_page_status(self, content: str, url: str) -> str:
        """Analyze Page Status"""
        content_lower = content.lower()

        # Success
        if any(kw in content_lower for kw in ["success", "verified", "congratulations", "veterans-claim"]):
            if "chatgpt.com" in url:
                return "success"

        # Need Email Link
        if any(kw in content_lower for kw in ["check your email", "sent you an email", "verify your email", "periksa email", "verifikasi email"]):
            return "need_email_link"

        # Already Verified
        if any(kw in content_lower for kw in ["already verified", "previously verified", "telah diverifikasi", "sudah diverifikasi"]):
            return "already_verified"

        # Invalid Info
        if any(kw in content_lower for kw in ["unable to verify", "could not verify", "invalid", "gagal memverifikasi", "tidak valid"]):
            return "invalid_info"

        # Need Login
        if "please log in" in content_lower or "must be logged in" in content_lower:
            return "need_login"

        # Rate Limited
        if "too many attempts" in content_lower or "try again later" in content_lower:
            return "rate_limited"

        # Limit Exceeded
        if any(kw in content_lower for kw in ["limit exceeded", "already redeemed", "attempted to redeem"]):
            return "limit_exceeded"

        return "unknown"

    # ==================== Complete Verification Workflow ====================

    async def run_verification(self, task: VerifyTask, email_manager, veteran_data_manager=None) -> bool:
        """
        Execute Complete Verification Workflow

        1. Initialize Browser
        2. Create Temporary Email
        3. Get Veteran Data (If veteran_data_manager provided)
        4. Register/Login ChatGPT
        5. Enter SheerID Verification
        6. Fill Form
        7. Submit and Wait for Validation
        8. Click Link to Complete
        """
        try:
            # 1. Initialize Browser
            if not await self.init_browser():
                task.status = VerifyStatus.FAILED
                task.error_message = "Browser initialization failed"
                task.error_type = "BROWSER_INIT_ERROR"
                return False

            # 2. Create Temporary Email (only if not already set)
            task.status = VerifyStatus.CREATING_EMAIL
            if not task.email:
                jwt, email = email_manager.create_email()
                if not email:
                    task.status = VerifyStatus.FAILED
                    task.error_message = "Failed to create email"
                    task.error_type = "EMAIL_CREATE_ERROR"
                    return False
                task.email = email
                task.password = self.generate_password()
                logger.info(f"[Task {task.task_id}] Created new email: {email}")
            else:
                logger.info(f"[Task {task.task_id}] Using existing email: {task.email}")

            # 3. Get Veteran Data
            if veteran_data_manager and not task.first_name:
                vet_data = veteran_data_manager.get_random_veteran()
                if vet_data:
                    task.first_name = vet_data["first_name"]
                    task.last_name = vet_data["last_name"]
                    task.birth_date = vet_data["birth_date"]
                    task.branch = vet_data["branch"]
                    task.discharge_date = vet_data["discharge_date"]
                    logger.info(f"[Task {task.task_id}] Using veteran data: {task.first_name} {task.last_name}, {task.branch}")

            # 4. Register/Login ChatGPT
            if not await self.register_chatgpt(task, email_manager):
                task.status = VerifyStatus.FAILED
                return False

            # 5. Enter SheerID Verification
            task.status = VerifyStatus.OPENING_SHEERID
            current_url = self.page.url
            
            # First, go back to veterans-claim page to get proper session
            # IMPORTANT: Must include ?redirectedFromAuth=true for page to detect logged-in state
            if "sheerid" not in current_url.lower() and "veterans" not in current_url.lower():
                logger.info(f"[Task {task.task_id}] Navigating back to veterans-claim page with auth redirect...")
                await self.page.goto(f"{self.VETERANS_CLAIM_URL}?redirectedFromAuth=true", timeout=60000)
                await asyncio.sleep(5.0)  # Wait longer for page to fully load
                await self.take_screenshot(task, "05b_veterans_page_after_login")
            
            # Check current URL after navigation
            current_url = self.page.url
            logger.info(f"[Task {task.task_id}] Current URL: {current_url}")
            
            # Look for verify button/link on the page
            if "sheerid" not in current_url.lower():
                logger.info(f"[Task {task.task_id}] Looking for Verify button...")
                
                # Wait for page content to stabilize
                await asyncio.sleep(2.0)
                
                # Take debug screenshot to see what's on the page
                await self.take_screenshot(task, "05b_looking_for_verify_btn")
                
                verify_selectors = [
                    'button.btn-primary:has-text("Verify eligibility")',
                    'button.btn-primary >> text="Verify eligibility"',
                    'button:has-text("Verify eligibility")',
                    'text="Verify eligibility"',
                    'a:has-text("Verify eligibility")',
                    'button:has-text("Verify your eligibility")',
                    '[data-testid*="verify"]',
                    'button:has-text("Verify")',
                    'a:has-text("Verify")',
                    'button:has-text("Start verification")',
                    'a[href*="sheerid"]',
                    'button:has-text("Claim")',
                    'a:has-text("Claim")',
                ]
                
                verify_btn = None
                for selector in verify_selectors:
                    try:
                        verify_btn = await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                        if verify_btn:
                            logger.info(f"[Task {task.task_id}] Found verify button: {selector}")
                            break
                    except:
                        continue
                
                # If verify button not found, check if there's a Login button (session not detected)
                if not verify_btn:
                    logger.warning(f"[Task {task.task_id}] Verify button not found, checking for Login button...")
                    try:
                        # Try reloading to refresh session state
                        logger.info(f"[Task {task.task_id}] Reloading page to refresh session...")
                        await self.page.reload(timeout=60000)
                        await asyncio.sleep(3.0)
                        
                        # Check for verify button again after reload
                        for selector in verify_selectors[:5]:  # Try top 5 selectors
                            try:
                                verify_btn = await self.page.wait_for_selector(selector, timeout=3000, state="visible")
                                if verify_btn:
                                    logger.info(f"[Task {task.task_id}] Found verify button after reload: {selector}")
                                    break
                            except:
                                continue
                        
                        # If still not found, try clicking Log in button which should auto-login
                        if not verify_btn:
                            login_btn = await self.page.query_selector('button:has-text("Log in"), a:has-text("Log in")')
                            if login_btn:
                                logger.info(f"[Task {task.task_id}] Found Login button, clicking to trigger auto-login...")
                                await login_btn.click()
                                await asyncio.sleep(5.0)
                                
                                # After login redirect, should be on SheerID or back on verify page
                                current_url = self.page.url
                                if "sheerid" in current_url.lower():
                                    logger.info(f"[Task {task.task_id}] Redirected to SheerID after login click!")
                                    verify_btn = True  # Mark as found to continue
                    except Exception as e:
                        logger.warning(f"[Task {task.task_id}] Error during session refresh: {e}")
                
                if verify_btn:
                    if verify_btn is not True:  # If it's actual button element
                        await verify_btn.click()
                        await asyncio.sleep(self.human.random_delay(5.0, 2.0))
                        await self.take_screenshot(task, "05c_after_verify_click")
                else:
                    logger.error(f"[Task {task.task_id}] Verify eligibility button NOT FOUND on veterans-claim page")
                    await self.take_screenshot(task, "error_no_verify_button")
                    task.error_message = "Verify eligibility button not found"
                    task.error_type = "VERIFY_BUTTON_NOT_FOUND"
                    return False
            
            await self.take_screenshot(task, "06_sheerid_page")

            if not await self.fill_sheerid_form(task):
                task.status = VerifyStatus.FAILED
                return False

            # 7. Submit and Wait for Verification
            task.status = VerifyStatus.CHECKING_RESULT
            success, result = await self.submit_and_wait_link(task, email_manager)

            if success:
                task.status = VerifyStatus.SUCCESS
                task.completed_at = datetime.now()
                logger.info(f"[Task {task.task_id}] Verification Successful!")
                await self.take_screenshot(task, "10_success")
                return True
            else:
                task.status = VerifyStatus.FAILED
                task.error_message = result
                logger.warning(f"[Task {task.task_id}] Verification Failed: {result}")
                await self.take_screenshot(task, "10_failed")
                return False

        except Exception as e:
            logger.error(f"[Task {task.task_id}] Verification Flow Exception: {e}")
            task.status = VerifyStatus.FAILED
            task.error_message = str(e)
            task.error_type = "UNEXPECTED_ERROR"
            await self.take_screenshot(task, "error_unexpected")
            return False

        finally:
            await self.close_browser()

    async def run_manual_sheerid_form(self, task: VerifyTask, sheerid_url: str, proxy: Optional[str] = None) -> bool:
        """
        Manual SheerID Form Fill (For manual trigger)
        1. Open URL
        2. Fill Form (using task data)
        3. Submit
        4. Wait for 'Check your email' or 'Success'
        """
        try:
            if not await self.init_browser(proxy=proxy):
                return False

            logger.info(f"[Manual] Opening SheerID URL: {sheerid_url}")
            await self.page.goto(sheerid_url, timeout=30000)
            await asyncio.sleep(3) # Wait for load

            # Fill Form (Includes Submit)
            if not await self.fill_sheerid_form(task):
                logger.error("[Manual] Failed to fill form")
                return False

            # Check Status after submission
            logger.info("[Manual] Form submitted, checking result...")
            for _ in range(15):
                await self.take_screenshot(task, f"manual_wait_{_}")
                content = await self.page.content()
                status = await self.analyze_page_status(content, self.page.url)
                
                logger.debug(f"[Manual] Status check: {status}")

                if status == "need_email_link":
                    logger.info("[Manual] Success: Verification email sent!")
                    return True
                
                if status == "success":
                    logger.info("[Manual] Success: Verified instantly!")
                    return True
                
                if status in ["already_verified", "limit_exceeded", "invalid_info"]:
                    logger.error(f"[Manual] Failed: {status}")
                    # Return True even if failed logic-wise, effectively "Task Done", 
                    # but caller might want False. 
                    # User said "just submission form". If we got a result, we return True (process finished).
                    # Actually, better to return False so UI shows "Failed".
                    return False
                    
                await asyncio.sleep(1.5)
            
            logger.warning("[Manual] Timeout waiting for submission result")
            return False

        except Exception as e:
            logger.error(f"[Manual] Exception: {e}")
            return False
        finally:
            await self.close_browser()

    async def run_email_token_verification(self, verification_url: str) -> bool:
        """
        Manual Email Token Verification
        1. Open Link
        2. Wait for confirmation
        """
        task = VerifyTask(task_id=f"manual-link-{int(time.time())}")
        try:
            if not await self.init_browser():
                return False

            logger.info(f"[ManualLink] Opening: {verification_url}")
            await self.page.goto(verification_url)
            
            # Wait for processing
            for _ in range(15):
                await asyncio.sleep(2.0)
                await self.take_screenshot(task, f"link_process_{_}")
                
                content = await self.page.content()
                status = await self.analyze_page_status(content, self.page.url)
                
                if status == "success":
                    logger.info("[ManualLink] Verification Success!")
                    return True
                
                if status in ["already_verified", "limit_exceeded", "invalid_info"]:
                    logger.error(f"[ManualLink] Failed: {status}")
                    return False
            
            return False
        except Exception as e:
             logger.error(f"[ManualLink] Exception: {e}")
             return False
        finally:
            await self.close_browser()



    async def get_sheerid_link_from_jwt(self, jwt_token: str, proxy: Optional[str] = None) -> Optional[str]:
        """
        Get SheerID Link using JWT
        1. Set session cookie
        2. Go to veterans-claim
        3. Click Verify
        4. Capture SheerID URL
        """
        task = VerifyTask(task_id=f"jwt-gen-{int(time.time())}")
        try:
            if not await self.init_browser(proxy=proxy):
                return None
            
            # Go to domain first to set context
            logger.info("[JWT] Navigating to domain root...")
            await self.page.goto("https://chatgpt.com")
            
            # --- Cookie Consent Handling (Before Auth) ---
            try:
                logger.info("[JWT] Checking for cookie consent banners (waiting 5s)...")
                
                # Wait for banner to possibly appear
                await asyncio.sleep(5.0) 
                
                cookie_selectors = [
                    'button:has-text("Accept all")',
                    'button:has-text("Accept")', 
                    'button:has-text("Allow")', 
                    'button:has-text("I agree")',
                    'button:has-text("OK")',
                    '[id*="cookie"] button',
                    '[class*="cookie"] button',
                    '#onetrust-accept-btn-handler'
                ]
                
                for selector in cookie_selectors:
                    try:
                        consent_btn = await self.page.query_selector(selector)
                        if consent_btn and await consent_btn.is_visible():
                            text = await consent_btn.inner_text()
                            logger.info(f"[JWT] Found cookie button: '{text}' ({selector}). Clicking...")
                            await consent_btn.click()
                            await asyncio.sleep(1.0) # Wait for animation
                            break # Clicked one, usually enough
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"[JWT] Cookie handling error: {e}")
            # -------------------------------

            await asyncio.sleep(1.0)

            logger.info("[JWT] Setting auth cookie...")
            await self.page.context.add_cookies([{
                "name": "__Secure-next-auth.session-token",
                "value": jwt_token,
                "domain": ".chatgpt.com",
                "path": "/",
                "secure": True,
                "sameSite": "Lax"
            }])
            
            # Navigate to target
            logger.info("[JWT] Navigating to veterans-claim...")

            await self.page.goto(self.VETERANS_CLAIM_URL)
            await asyncio.sleep(self.human.random_delay(4.0, 2.0))
            
            # Debug: Check where we are
            current_url = self.page.url
            page_title = await self.page.title()
            logger.info(f"[JWT] Page loaded. URL: {current_url}, Title: {page_title}")

            # Click Verify Button
            verify_selectors = [
                 'button:has-text("Verify eligibility")',
                 'button:has-text("Verify your eligibility")',
                 'button:has-text("Verify")',
                 '[data-testid*="verify"]'
            ]
            
            verify_btn = None
            for selector in verify_selectors:
                if await self.page.query_selector(selector):
                    verify_btn = await self.page.query_selector(selector)
                    break
            
            if verify_btn:
                logger.info("[JWT] Found verify button, clicking...")
                
                # Listen for new page or request
                async with self.page.expect_navigation(url=lambda u: "sheerid.com" in u, timeout=15000) as response_info:
                    await verify_btn.click()
                
                # Wait a bit for redirect to settle
                await asyncio.sleep(2.0)
                
                current_url = self.page.url
                if "sheerid.com" in current_url:
                    logger.info(f"[JWT] Captured SheerID URL: {current_url}")
                    return current_url
                else:
                    logger.warning(f"[JWT] Redirected to {current_url}, expected SheerID")
                    # Fallback: check if we are on SheerID now (maybe navigation happened fast)
                    if "sheerid" in current_url:
                         return current_url
            else:
                logger.error("[JWT] Verify button not found. Session might be invalid.")
                
                # Check if we are on login page
                content = await self.page.content()
                if "Log in" in content or "Sign up" in content:
                    logger.error("[JWT] Detected Login page - Authentication Failed")
                    return "ERROR: Auth Failed. Invalid Session Cookie."

            return None

        except Exception as e:
            logger.error(f"[JWT] Exception: {e}")
            return None
        finally:
            await self.close_browser()

    @staticmethod
    def generate_password() -> str:
        """Generate random password (meets OpenAI requirements: 12+ chars)"""
        import string
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(random.choices(chars, k=16))
        return password


# ==================== Test ====================

async def test_worker():
    """Test Browser Worker"""
    from veteran_data import VeteranDataManager

    logging.basicConfig(level=logging.INFO)

    # Init data manager
    data_manager = VeteranDataManager()
    vet_data = data_manager.get_random_veteran()

    if vet_data:
        print(f"\nTest Data:")
        print(f"  Name: {vet_data['first_name']} {vet_data['last_name']}")
        print(f"  Birthday: {vet_data['birth_date']}")
        print(f"  Branch: {vet_data['branch']}")
        print(f"  Discharge: {vet_data['discharge_date']}")

    task = VerifyTask(
        task_id="test-001",
        first_name=vet_data["first_name"] if vet_data else "John",
        last_name=vet_data["last_name"] if vet_data else "Smith",
        branch=vet_data["branch"] if vet_data else "Army",
        birth_date=vet_data["birth_date"] if vet_data else {"month": "March", "day": "15", "year": "1985"},
        discharge_date=vet_data["discharge_date"] if vet_data else {"month": "August", "day": "20", "year": "2024"},
    )

    worker = BrowserWorker(headless=False, screenshot_dir="screenshots")
    print(f"\nTask: {task}")

    # Only init browser and open page for testing
    if await worker.init_browser():
        await worker.page.goto(BrowserWorker.VETERANS_CLAIM_URL)
        print("\nBrowser opened Veterans Claim page, manual testing available")
        input("Press Enter to close browser...")
        await worker.close_browser()


if __name__ == "__main__":
    asyncio.run(test_worker())
