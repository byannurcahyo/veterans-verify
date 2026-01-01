"""
Veterans Verify - Email Management
Reused from test_band_gemini_mail project

Supports:
1. Create temporary email
2. Extract OpenAI/ChatGPT verification code
3. Extract SheerID verification link
"""
import re
import time
import random
import string
from typing import Optional, Tuple, List
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import unquote

import requests
import logging

logger = logging.getLogger(__name__)


class EmailManager:
    """Email Manager"""

    def __init__(self, worker_domain: str, email_domain: str, admin_password: str):
        self.worker_domain = worker_domain
        self.email_domain = email_domain
        self.admin_password = admin_password

    @staticmethod
    def generate_random_name() -> str:
        """Generate random email name"""
        letters1 = ''.join(random.choices(string.ascii_lowercase, k=4))
        numbers = ''.join(random.choices(string.digits, k=2))
        letters2 = ''.join(random.choices(string.ascii_lowercase, k=3))
        return letters1 + numbers + letters2

    def create_email(self, username: str = "") -> Tuple[Optional[str], Optional[str]]:
        """Create email, return (jwt, email_address)"""
        try:
            name = username if username else self.generate_random_name()

            res = requests.post(
                f"https://{self.worker_domain}/admin/new_address",
                json={
                    "enablePrefix": True,
                    "name": name,
                    "domain": self.email_domain,
                },
                headers={
                    'x-admin-auth': self.admin_password,
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if res.status_code == 200:
                data = res.json()
                return data.get('jwt'), data.get('address')
            else:
                logger.error(f"Failed to create email: HTTP {res.status_code}")
                # Fallback to mock email if using dummy config or connection failed
                if "dummy" in self.worker_domain or "localhost" in self.worker_domain or True:
                    logger.warning("[Mock] Using mock email (HTTP Error Fallback)")
                    mock_name = username if username else self.generate_random_name()
                    return "mock_jwt_token", f"{mock_name}@{self.email_domain}"
                return None, None
        except Exception as e:
            logger.error(f"Error creating email: {e}")
            # Fallback to mock email if using dummy config or connection failed
            if "dummy" in self.worker_domain or "localhost" in self.worker_domain or True: # Force mock for now as requested
                logger.warning("[Mock] Using mock email for testing")
                mock_name = username if username else self.generate_random_name()
                return "mock_jwt_token", f"{mock_name}@{self.email_domain}"
            return None, None

    def _get_recent_emails(self, email: str, limit: int = 10) -> List[dict]:
        """Get recent email list"""
        try:
            api_url = f"https://{self.worker_domain}/admin/mails"
            res = requests.get(
                api_url,
                params={"limit": limit, "offset": 0, "address": email},
                headers={
                    "x-admin-auth": self.admin_password,
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if res.status_code == 200:
                data = res.json()
                return data.get('results') or []
            return []
        except Exception as e:
            logger.error(f"Failed to get email list: {e}")
            return []

    def _is_recent_email(self, raw_content: str, max_age_minutes: int = 30) -> bool:
        """Check if email is recent"""
        try:
            received_match = re.search(r'Received:.*?;\s*(.*?)\r\n', raw_content, re.DOTALL)
            if received_match:
                date_str = received_match.group(1).strip()
                email_time = parsedate_to_datetime(date_str)
                current_time = datetime.now(timezone.utc)
                diff = current_time - email_time
                logger.debug(f"Email age: {diff} (Max: {timedelta(minutes=max_age_minutes)})")
                
                return diff <= timedelta(minutes=max_age_minutes)
        except Exception as e:
            logger.warning(f"Failed to parse email time: {e}")
        return True  # If unable to parse time, default to recent

    def _clean_email_content(self, raw_content: str) -> str:
        """Clean email content (handle quoted-printable encoding etc.)"""
        content = raw_content.replace('=\r\n', '').replace('=\n', '')
        content = content.replace('=3D', '=')
        content = content.replace('=26', '&')
        content = content.replace('=3A', ':')
        content = content.replace('=2F', '/')
        return content

    def check_verification_code(self, email: str, max_retries: int = 20, interval: float = 3.0) -> Optional[str]:
        """
        Check verification code email (for ChatGPT/OpenAI registration)

        ChatGPT code format:
        - Subject: "Your ChatGPT code is XXXXXX"
        - Body: May also contain verification code
        """
        for attempt in range(max_retries):
            try:
                emails = self._get_recent_emails(email, limit=5)

                for email_data in emails:
                    raw_content = email_data.get('raw') or ''
                    if not raw_content:
                        continue

                    # Check if it is a recent email
                    if not self._is_recent_email(raw_content):
                        logger.debug("Ignore expired email")
                        continue

                    # Clean content
                    cleaned_content = self._clean_email_content(raw_content)

                    # [P0 Fix] Prioritize extracting code from Subject
                    subject_patterns = [
                        # Chinese format: 你的 ChatGPT 代码为 XXXXXX
                        r'Subject:.*?代码为\s*([A-Z0-9]{6})',
                        r'Subject:.*?验证码[：:\s]*([A-Z0-9]{6})',
                        # English format: Your ChatGPT code is XXXXXX
                        r'Subject:.*?code\s+is\s+([A-Z0-9]{6})',
                        r'Subject:.*?code[：:\s]+([A-Z0-9]{6})',
                    ]
                    for pattern in subject_patterns:
                        match = re.search(pattern, raw_content, re.IGNORECASE | re.DOTALL)
                        if match:
                            code = match.group(1).upper()
                            if len(code) == 6 and code.isalnum():
                                logger.info(f"Found verification code in Subject: {code}")
                                return code

                    # OpenAI/ChatGPT verification code extraction pattern (Body)
                    patterns = [
                        # OpenAI Common format
                        r'verification code[:\s]+([A-Z0-9]{6})',
                        r'code[:\s]+([A-Z0-9]{6})',
                        r'>([A-Z0-9]{6})<',
                        # Universal 6-digit code
                        r'class=["\']?verification-code["\']?[^>]*>([A-Z0-9]{6})',
                        r'font-size:\s*\d+px[^>]*>([A-Z0-9]{6})<',
                        # Numeric code
                        r'verification code[:\s]+(\d{6})',
                        r'>(\d{6})<',
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, cleaned_content, re.IGNORECASE | re.DOTALL)
                        if match:
                            code = match.group(1).upper()
                            if len(code) == 6 and code.isalnum():
                                logger.info(f"Found verification code: {code}")
                                return code

                    # Fallback: Check if it contains verification related keywords
                    lowered = cleaned_content.lower()
                    keywords = ["verification", "verify", "code", "openai", "chatgpt"]
                    if any(kw in lowered for kw in keywords):
                        m = re.search(r'\b([A-Z0-9]{6})\b', cleaned_content, re.IGNORECASE)
                        if m:
                            code = m.group(1).upper()
                            if len(code) == 6 and code.isalnum():
                                logger.info(f"Found verification code (Fallback): {code}")
                                return code

                logger.debug(f"Waiting for verification code... ({attempt + 1}/{max_retries})")
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error checking verification code: {e}")
                time.sleep(interval)

        logger.warning("Failed to get verification code")
        return None

    def check_verification_link(self, email: str, max_retries: int = 30, interval: float = 3.0) -> Optional[str]:
        """
        Check verification link email (for SheerID verification)

        SheerID sends emails containing verification links, format like:
        - https://services.sheerid.com/verify/...
        - Or https://my.sheerid.com/...
        """
        for attempt in range(max_retries):
            try:
                emails = self._get_recent_emails(email, limit=10)

                for email_data in emails:
                    raw_content = email_data.get('raw') or ''
                    if not raw_content:
                        continue

                    # 检查是否是最近的邮件
                    if not self._is_recent_email(raw_content):
                        continue

                    # Check if sender is SheerID
                    from_match = re.search(r'From:.*?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw_content, re.IGNORECASE)
                    if from_match:
                        sender = from_match.group(1).lower()
                        if 'sheerid' not in sender and 'verify' not in sender:
                            # Not SheerID email, skip
                            continue

                    # Clean content
                    cleaned_content = self._clean_email_content(raw_content)

                    # SheerID verification link extraction patterns
                    link_patterns = [
                        # SheerID verification link
                        r'(https?://(?:services|my)\.sheerid\.com/verify/[^\s"\'<>]+)',
                        r'(https?://[^\s"\'<>]*sheerid[^\s"\'<>]*verify[^\s"\'<>]+)',
                        # Link with token
                        r'(https?://[^\s"\'<>]+verificationId=[^\s"\'<>]+)',
                        # Link in href attribute
                        r'href=["\'](https?://[^\s"\'<>]*sheerid[^\s"\'<>]+)["\']',
                        r'href=3D["\'](https?://[^\s"\'<>]*sheerid[^\s"\'<>]+)["\']',
                    ]

                    for pattern in link_patterns:
                        matches = re.findall(pattern, cleaned_content, re.IGNORECASE)
                        for match in matches:
                            link = match if isinstance(match, str) else match[0]
                            # Decode URL
                            link = unquote(link)
                            # Clean invalid characters at end of link (quotes, brackets, punctuation)
                            link = re.sub(r'["\'>]+$', '', link)
                            link = link.rstrip(').,;]')
                            
                            # Validate link format
                            if 'sheerid' in link.lower() and ('verify' in link.lower() or 'verification' in link.lower()):
                                logger.info(f"Found verification link: {link[:80]}...")
                                return link

                logger.debug(f"Waiting for verification link... ({attempt + 1}/{max_retries})")
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error checking verification link: {e}")
                time.sleep(interval)

        logger.warning("Failed to get verification link")
        return None

    def get_all_links_from_email(self, email: str, sender_filter: str = None) -> List[str]:
        """
        Get all links from email (for debugging)

        Args:
            email: Email address
            sender_filter: Optional sender filter (e.g. 'sheerid')
        """
        links = []
        try:
            emails = self._get_recent_emails(email, limit=5)

            for email_data in emails:
                raw_content = email_data.get('raw') or ''
                if not raw_content:
                    continue

                # Sender filter
                if sender_filter:
                    from_match = re.search(r'From:.*?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw_content, re.IGNORECASE)
                    if from_match:
                        sender = from_match.group(1).lower()
                        if sender_filter.lower() not in sender:
                            continue

                cleaned_content = self._clean_email_content(raw_content)

                # Extract all https links
                found_links = re.findall(r'(https?://[^\s"\'<>]+)', cleaned_content)
                for link in found_links:
                    link = unquote(link)
                    link = re.sub(r'["\'>]+$', '', link)
                    if link not in links:
                        links.append(link)

        except Exception as e:
            logger.error(f"Error getting email links: {e}")

        return links
