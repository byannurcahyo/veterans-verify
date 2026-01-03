"""
Veterans Verify - Account Management Module

Reference test_band_gemini_mail project architecture
Implement bulk temporary email creation + ChatGPT registration + Veterans verification
"""
import os
import json
import threading
import queue
import time
import random
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AccountStatus(Enum):
    """Account Status"""
    PENDING = "pending"                    # Pending
    CREATING_EMAIL = "creating_email"      # Creating Email
    REGISTERING_CHATGPT = "registering"    # Registering ChatGPT
    WAITING_CHATGPT_CODE = "waiting_code"  # Waiting for ChatGPT Code
    CHATGPT_READY = "chatgpt_ready"        # ChatGPT Ready
    OPENING_SHEERID = "opening_sheerid"    # Opening SheerID Page
    FILLING_FORM = "filling_form"          # Filling Form
    WAITING_VERIFY_LINK = "waiting_link"   # Waiting for Verification Link
    CLICKING_LINK = "clicking_link"        # Clicking Verification Link
    SUCCESS = "success"                    # Success
    FAILED = "failed"                      # Failed


@dataclass
class AccountInfo:
    """Account Info"""
    # Basic Info
    account_id: str = ""               # Unique ID
    email: str = ""                    # Temp Email
    password: str = ""                 # ChatGPT Password
    jwt: str = ""                      # Email JWT

    # Veteran Info (From BIRLS)
    first_name: str = ""
    last_name: str = ""
    branch: str = ""                   # Branch
    birth_date: Dict[str, str] = field(default_factory=dict)      # {"month": "March", "day": "15", "year": "1985"}
    discharge_date: Dict[str, str] = field(default_factory=dict)  # {"month": "June", "day": "20", "year": "2024"}

    # Status
    status: AccountStatus = AccountStatus.PENDING
    error_message: str = ""
    error_type: str = ""               # Error Classification

    # Profile 相关
    profile_id: str = ""
    profile_group: str = ""
    proxy: str = ""

    # Timestamp
    created_at: str = ""
    updated_at: str = ""

    # Config
    email_config: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dict (for API return)"""
        return {
            "account_id": self.account_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "branch": self.branch,
            "birth_date": self.birth_date,
            "discharge_date": self.discharge_date,
            "status": self.status.value,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "profile_id": self.profile_id,
            "proxy": self.proxy,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_storage_dict(self) -> Dict:
        """Convert to storage dict"""
        return {
            "account_id": self.account_id,
            "email": self.email,
            "password": self.password,
            "jwt": self.jwt,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "branch": self.branch,
            "birth_date": self.birth_date,
            "discharge_date": self.discharge_date,
            "status": self.status.value,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "profile_id": self.profile_id,
            "profile_group": self.profile_group,
            "proxy": self.proxy,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_storage_dict(cls, data: Dict, email_config: Optional[Dict] = None) -> "AccountInfo":
        """Restore from storage dict"""
        status_val = data.get("status", "pending")
        try:
            status = AccountStatus(status_val)
        except ValueError:
            status = AccountStatus.PENDING

        return cls(
            account_id=data.get("account_id", ""),
            email=data.get("email", ""),
            password=data.get("password", ""),
            jwt=data.get("jwt", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            branch=data.get("branch", ""),
            birth_date=data.get("birth_date", {}),
            discharge_date=data.get("discharge_date", {}),
            status=status,
            error_message=data.get("error_message", ""),
            error_type=data.get("error_type", ""),
            profile_id=data.get("profile_id", ""),
            profile_group=data.get("profile_group", ""),
            proxy=data.get("proxy", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            email_config=email_config or {},
        )


class AccountManager:
    """
    Account Manager

    Features:
    1. Batch create temporary emails
    2. Manage account queue
    3. Schedule browser workers
    4. Persist account data
    5. Stop-loss mechanism
    """

    def __init__(self, config, veteran_data_manager=None):
        self.config = config
        self.veteran_data_manager = veteran_data_manager

        # Account storage
        self.accounts: Dict[str, AccountInfo] = {}  # email -> AccountInfo
        self.manual_tasks: List[Dict] = []          # List of manual task records
        self.accounts_lock = threading.Lock() # Existing lock for accounts
        self.lock = threading.Lock() # New general lock as per instruction

        # Worker management
        self.workers: Dict[int, Any] = {}
        self.workers_lock = threading.Lock()

        # Task queue
        self.task_queue = queue.Queue()

        # Stop-loss status
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._cooldown_lock = threading.Lock()

        # Persistence
        self._persist_enabled = os.getenv("PERSIST_DATA", "false").lower() == "true"
        self._accounts_file = os.getenv("ACCOUNTS_FILE", "./data/accounts.json")
        self._save_lock = threading.Lock()
        self._last_save_time = 0.0

        # Load saved accounts
        self._load_accounts()

        # Start background task processor
        self._start_task_processor()

    # ==================== Account Creation ====================

    def create_account(
        self,
        profile_group: str = "",
        profile_id: str = "",
        async_mode: bool = True
    ) -> (Optional[AccountInfo], Optional[str]):
        """
        Create single account

        Flow:
        1. Create temporary email
        2. Get veteran data
        3. Add to verification queue
        """
        from email_manager import EmailManager
        import uuid

        # 1. Get email config
        email_config = self.config.get_random_email_config()
        if not email_config:
            return None, "Email service not configured"

        # 2. Create temporary email
        email_manager = EmailManager(
            email_config["worker_domain"],
            email_config["email_domain"],
            email_config["admin_password"]
        )
        jwt, email = email_manager.create_email()
        if not jwt or not email:
            return None, "Failed to create email"

        # 3. Get veteran data
        vet_data = None
        if self.veteran_data_manager:
            vet_data = self.veteran_data_manager.get_random_veteran()

        if not vet_data:
            return None, "Failed to get veteran data"

        # 4. Generate password
        password = self._generate_password()

        # 5. Create account object
        account = AccountInfo(
            account_id=str(uuid.uuid4())[:8],
            email=email,
            password=password,
            jwt=jwt,
            first_name=vet_data["first_name"],
            last_name=vet_data["last_name"],
            branch=vet_data["branch"],
            birth_date=vet_data["birth_date"],
            discharge_date=vet_data["discharge_date"],
            status=AccountStatus.PENDING,
            profile_id=profile_id,
            profile_group=profile_group,
            proxy=self.config.get_proxy_server(),
            created_at=datetime.now().isoformat(),
            email_config=email_config,
        )

        # 6. Save account
        with self.accounts_lock:
            self.accounts[email] = account
        self._save_accounts()

        logger.info(f"[AccountManager] Created account: {email}, Veteran: {account.first_name} {account.last_name}")

        # 7. Add to queue
        if async_mode:
            self._enqueue_task(account)
            return account, None
        else:
            # Sync mode: Start worker directly
            worker_id = self._get_available_worker_slot()
            if worker_id is None:
                self._enqueue_task(account)
                return account, "Added to queue, waiting for execution"
            self._start_worker(worker_id, account)
            return account, None

    def batch_create_accounts(
        self,
        count: int,
        interval: float = 0,
        profile_group: str = "",
    ) -> int:
        """
        Batch create accounts (background thread)
        """
        def _batch_task():
            created = 0
            for i in range(count):
                account, error = self.create_account(
                    profile_group=profile_group,
                    async_mode=True
                )
                if account:
                    created += 1
                    logger.info(f"[Batch] Created account {i+1}/{count}: {account.email}")
                else:
                    logger.warning(f"[Batch] Creation failed {i+1}/{count}: {error}")

                if interval > 0 and i < count - 1:
                    time.sleep(interval)

            logger.info(f"[Batch] Batch creation completed: {created}/{count}")

        thread = threading.Thread(target=_batch_task, daemon=True)
        thread.start()
        return count

    # ==================== Worker Management ====================

    def _get_available_worker_slot(self) -> Optional[int]:
        """Get available worker slot"""
        max_workers = self.config.get_max_workers()
        with self.workers_lock:
            active_count = sum(1 for w in self.workers.values() if hasattr(w, 'is_alive') and w.is_alive())
            if active_count >= max_workers:
                return None
            for i in range(max_workers):
                if i not in self.workers or not self.workers[i].is_alive():
                    return i
        return None

    def _start_worker(self, worker_id: int, account: AccountInfo):
        """Start worker"""
        from browser_worker import BrowserWorker, VerifyTask

        # Create verification task
        task = VerifyTask(
            task_id=account.account_id,
            email=account.email,
            password=account.password,
            first_name=account.first_name,
            last_name=account.last_name,
            branch=account.branch,
            birth_date=account.birth_date,
            discharge_date=account.discharge_date,
        )

        # Create worker
        worker = BrowserWorker(
            headless=self.config.get_headless(),
            screenshot_dir=self.config.get_debug_screenshot_dir(),
        )

        # Run async (need to run event loop in new thread)
        def _run_worker():
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                from email_manager import EmailManager
                email_manager = EmailManager(
                    account.email_config.get("worker_domain", ""),
                    account.email_config.get("email_domain", ""),
                    account.email_config.get("admin_password", ""),
                )

                success = loop.run_until_complete(
                    worker.run_verification(task, email_manager, self.veteran_data_manager)
                )

                # Update account status
                with self.accounts_lock:
                    if account.email in self.accounts:
                        acc = self.accounts[account.email]
                        if success:
                            acc.status = AccountStatus.SUCCESS
                            self._on_success()
                        else:
                            acc.status = AccountStatus.FAILED
                            acc.error_message = task.error_message
                            acc.error_type = task.error_type
                            self._on_failure()
                        acc.updated_at = datetime.now().isoformat()

                self._save_accounts()
                self._on_worker_complete(worker_id, account.email, success)

            except Exception as e:
                logger.error(f"[Worker {worker_id}] Exception: {e}")
                with self.accounts_lock:
                    if account.email in self.accounts:
                        self.accounts[account.email].status = AccountStatus.FAILED
                        self.accounts[account.email].error_message = str(e)
                self._on_failure()
                self._save_accounts()

        thread = threading.Thread(target=_run_worker, daemon=True)
        with self.workers_lock:
            self.workers[worker_id] = thread
        thread.start()

    def _on_worker_complete(self, worker_id: int, email: str, success: bool):
        """Worker complete callback"""
        with self.workers_lock:
            if worker_id in self.workers:
                del self.workers[worker_id]

        logger.info(f"[Worker {worker_id}] Finished: {email}, Success={success}")

    # ==================== Manual Verification Tasks ====================

    def run_manual_sheerid_task(self, sheerid_url: str, email: str, proxy: Optional[str] = None) -> bool:
        """Run manual SheerID submission task"""
        # Record Task
        task_id = self._add_manual_task("SUBMIT_FORM", f"{email} | {sheerid_url[:20]}...", proxy or "Direct")
        
        from browser_worker import BrowserWorker, VerifyTask
        from veteran_data import VeteranDataManager
        import asyncio

        def _run_task():
            logger.info(f"[Manual] Starting SheerID task for {email} (Proxy: {proxy})")
            
            # Get Veteran Data
            vet_manager = VeteranDataManager() # Or reuse self.veteran_data_manager
            vet_data = vet_manager.get_random_veteran()
            
            if not vet_data:
                logger.error("[Manual] No veteran data available")
                self._update_manual_task(task_id, "FAILED", "No veteran data")
                return

            task = VerifyTask(
                task_id=f"manual-{email.split('@')[0]}",
                email=email,
                first_name=vet_data["first_name"],
                last_name=vet_data["last_name"],
                branch=vet_data["branch"],
                birth_date=vet_data["birth_date"],
                discharge_date=vet_data["discharge_date"]
            )

            worker = BrowserWorker(
                headless=self.config.get_headless(),
                screenshot_dir=self.config.get_debug_screenshot_dir()
            )

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Pass proxy to init_browser if supported or manually init
                # We need to manually set it on the worker or pass to run method if supported
                # Updating worker init logic dynamically:
                success = loop.run_until_complete(worker.run_manual_sheerid_form(task, sheerid_url, proxy=proxy))
                logger.info(f"[Manual] SheerID task finished. Success: {success}")
                self._update_manual_task(task_id, "SUCCESS" if success else "FAILED", "Form Submitted (Email sent)" if success else "Failed (Check logs)")
            except Exception as e:
                logger.error(f"[Manual] Task failed: {e}")
                self._update_manual_task(task_id, "ERROR", str(e))
            finally:
                loop.close()

        thread = threading.Thread(target=_run_task, daemon=True)
        thread.start()
        return True

    def run_manual_token_task(self, verify_url: str, proxy: Optional[str] = None):
        """Run manual token verification task"""
        from browser_worker import BrowserWorker, VerifyTask
        import asyncio
        
        task_id = self._add_manual_task("VERIFY_TOKEN", verify_url[:40] + "...", proxy or "Direct")
        logger.info(f"[Manual] Starting Token task for {verify_url}")

        def _run_task():
            logger.info(f"[Manual] Starting Token Verify task for {verify_url} (Proxy: {proxy})")

            task = VerifyTask(
                task_id=task_id,
                email="manual-token", 
                first_name="", last_name="", branch="", birth_date={}, discharge_date={}
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            worker = BrowserWorker(headless=self.config.get_headless(), screenshot_dir=self.config.get_debug_screenshot_dir())
            try:
                # Note: run_email_token_verification was added to BrowserWorker in previous step
                success = loop.run_until_complete(worker.run_manual_token_verify(task, verify_url, proxy=proxy))
                logger.info(f"[Manual] Token task finished. Success: {success}")
                self._update_manual_task(task_id, "SUCCESS" if success else "FAILED", "Verified" if success else "Failed")
            except Exception as e:
                logger.error(f"[Manual] Task failed: {e}")
                self._update_manual_task(task_id, "ERROR", str(e))
            finally:
                loop.close()

        thread = threading.Thread(target=_run_task, daemon=True)
        thread.start()
        return True

    def run_manual_generate_sheerid_task(self, jwt_token: str, proxy: Optional[str] = None) -> bool:
        """Run manual SheerID generation task"""
        
        from browser_worker import BrowserWorker
        
        self.manual_gen_status = "running"
        self.manual_gen_result = None
        
        # Record Task
        task_id = self._add_manual_task("GENERATE_LINK", jwt_token[:20] + "...", proxy or "Direct")
        
        logger.info(f"[Manual] Starting SheerID Generation task (Proxy: {proxy})")
        
        def _run_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            worker = BrowserWorker(headless=self.config.get_headless(), screenshot_dir=self.config.get_debug_screenshot_dir())
            try:
                link = loop.run_until_complete(worker.get_sheerid_link_from_jwt(jwt_token, proxy=proxy))
                if link:
                    logger.info(f"[Manual] GENERATED LINK: {link}")
                    self.manual_gen_result = link
                    self.manual_gen_status = "success"
                    self._update_manual_task(task_id, "SUCCESS", link)
                else:
                    logger.error("[Manual] Failed to generate link")
                    self.manual_gen_status = "failed"
                    self.manual_gen_result = "Could not capture link (Check logs/proxy)"
                    self._update_manual_task(task_id, "FAILED", "Could not capture link")
            except Exception as e:
                logger.error(f"[Manual] Gen Task failed: {e}")
                self.manual_gen_status = "error"
                self.manual_gen_result = f"Error: {str(e)}"
                self._update_manual_task(task_id, "ERROR", str(e))
            finally:
                loop.close()

        thread = threading.Thread(target=_run_task, daemon=True)
        thread.start()
        return True

    # ==================== Task Queue ====================

    def _enqueue_task(self, account: AccountInfo):
        """Add to task queue"""
        self.task_queue.put(account)

    def _start_task_processor(self):
        """Start background task processor"""
        def _processor():
            while True:
                try:
                    # Check cooldown
                    with self._cooldown_lock:
                        if time.time() < self._cooldown_until:
                            remaining = self._cooldown_until - time.time()
                            logger.info(f"[TaskProcessor] Cooling down, remaining {remaining:.0f}s")
                            time.sleep(min(5, remaining))
                            continue

                    # Get task
                    try:
                        account = self.task_queue.get(timeout=1)
                    except queue.Empty:
                        continue

                    # Get worker slot
                    worker_id = self._get_available_worker_slot()
                    if worker_id is not None:
                        self._start_worker(worker_id, account)
                    else:
                        # Put back to queue
                        self.task_queue.put(account)
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"[TaskProcessor] Error: {e}")
                    time.sleep(1)

        thread = threading.Thread(target=_processor, daemon=True)
        thread.start()

    # ==================== Stop-loss Mechanism ====================

    def _on_success(self):
        """Reset consecutive failures on success"""
        with self._cooldown_lock:
            self._consecutive_failures = 0

    def _on_failure(self):
        """Check cooldown on failure"""
        with self._cooldown_lock:
            self._consecutive_failures += 1
            max_failures = self.config.get_max_consecutive_failures()

            if self._consecutive_failures >= max_failures:
                cooldown_min, cooldown_max = self.config.get_cooldown_range()
                cooldown = random.randint(cooldown_min, cooldown_max)
                self._cooldown_until = time.time() + cooldown
                self._consecutive_failures = 0
                logger.warning(f"[StopLoss] Consecutive failures {max_failures}, cooldown {cooldown}s")

    # ==================== Persistence ====================

    def _add_manual_task(self, task_type: str, input_data: str, proxy: str = "") -> str:
        """Add a manual task record and return its ID"""
        task_id = f"task_{int(time.time())}_{random.randint(1000,9999)}"
        record = {
            "id": task_id,
            "type": task_type,
            "input": input_data,
            "proxy": proxy,
            "status": "RUNNING",
            "result": "",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        with self.lock:
            self.manual_tasks.insert(0, record)
            # Keep only last 50
            if len(self.manual_tasks) > 50:
                self.manual_tasks.pop()
        return task_id

    def _update_manual_task(self, task_id: str, status: str, result: str = ""):
        """Update a manual task record"""
        with self.lock:
            for task in self.manual_tasks:
                if task["id"] == task_id:
                    task["status"] = status
                    task["result"] = result
                    break

    def _save_accounts(self, force: bool = False):
        """Save accounts to disk"""
        if not self._persist_enabled:
            return

        debounce = float(os.getenv("SAVE_DEBOUNCE_SECONDS", "1.0"))
        now = time.time()
        if not force and (now - self._last_save_time) < debounce:
            return

        with self._save_lock:
            if not force and (now - self._last_save_time) < debounce:
                return

            try:
                path = Path(self._accounts_file)
                path.parent.mkdir(parents=True, exist_ok=True)

                with self.accounts_lock:
                    payload = {
                        "saved_at": datetime.now().isoformat(),
                        "accounts": [acc.to_storage_dict() for acc in self.accounts.values()]
                    }

                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                self._last_save_time = now
                logger.debug(f"[Persist] Saved {len(self.accounts)} accounts")

            except Exception as e:
                logger.error(f"[Persist] Save failed: {e}")

    def _load_accounts(self):
        """Load accounts from disk"""
        if not self._persist_enabled:
            return

        path = Path(self._accounts_file)
        if not path.exists():
            return

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = raw.get("accounts") if isinstance(raw, dict) else raw
            if not isinstance(items, list):
                return

            loaded = 0
            with self.accounts_lock:
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    email = item.get("email", "").strip()
                    if not email:
                        continue

                    # Get corresponding email config
                    email_config = self._get_email_config_by_domain(email)
                    account = AccountInfo.from_storage_dict(item, email_config)
                    self.accounts[email] = account
                    loaded += 1

            logger.info(f"[Persist] Loaded {loaded} accounts")

        except Exception as e:
            logger.error(f"[Persist] Load failed: {e}")

    def _get_email_config_by_domain(self, email: str) -> Optional[Dict]:
        """Get config by email domain"""
        if "@" not in email:
            return None
        domain = email.split("@")[1].lower()
        for cfg in self.config.get_email_configs():
            if cfg.get("email_domain", "").lower() == domain:
                return cfg
        return None

    # ==================== Utils ====================

    @staticmethod
    def _generate_password() -> str:
        """Generate random password (12+ chars)"""
        import string
        chars = string.ascii_letters + string.digits + "!@#$%"
        return "".join(random.choices(chars, k=16))

    # ==================== Account Operations ====================

    def get_accounts(
        self,
        status_filter: str = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict:
        """Get account list"""
        with self.accounts_lock:
            accounts_list = list(self.accounts.values())

        # Filter
        if status_filter:
            if status_filter == "success":
                accounts_list = [a for a in accounts_list if a.status == AccountStatus.SUCCESS]
            elif status_filter == "failed":
                accounts_list = [a for a in accounts_list if a.status == AccountStatus.FAILED]
            elif status_filter == "pending":
                accounts_list = [a for a in accounts_list if a.status not in [AccountStatus.SUCCESS, AccountStatus.FAILED]]

        # Statistics
        total = len(accounts_list)
        success_count = sum(1 for a in self.accounts.values() if a.status == AccountStatus.SUCCESS)
        failed_count = sum(1 for a in self.accounts.values() if a.status == AccountStatus.FAILED)
        pending_count = len(self.accounts) - success_count - failed_count

        # Pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated = accounts_list[start:end]

        return {
            "accounts": [a.to_dict() for a in paginated],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1,
            "stats": {
                "total": len(self.accounts),
                "success": success_count,
                "failed": failed_count,
                "pending": pending_count,
            }
        }

    def get_account(self, email: str) -> Optional[AccountInfo]:
        """Get single account"""
        with self.accounts_lock:
            return self.accounts.get(email)

    def delete_account(self, email: str) -> bool:
        """Delete account"""
        with self.accounts_lock:
            if email in self.accounts:
                del self.accounts[email]
                self._save_accounts(force=True)
                return True
        return False

    def retry_account(self, email: str) -> bool:
        """Retry failed account"""
        with self.accounts_lock:
            if email not in self.accounts:
                return False
            account = self.accounts[email]
            if account.status != AccountStatus.FAILED:
                return False

            # Reset status
            account.status = AccountStatus.PENDING
            account.error_message = ""
            account.error_type = ""

        # Add to queue
        self._enqueue_task(account)
        self._save_accounts()
        return True

    def get_status(self) -> Dict:
        """Get system status"""
        with self.accounts_lock:
            total = len(self.accounts)
            success = sum(1 for a in self.accounts.values() if a.status == AccountStatus.SUCCESS)
            failed = sum(1 for a in self.accounts.values() if a.status == AccountStatus.FAILED)
            pending = total - success - failed

        with self.workers_lock:
            active_workers = sum(1 for w in self.workers.values() if hasattr(w, 'is_alive') and w.is_alive())

        with self._cooldown_lock:
            cooldown_remaining = max(0, self._cooldown_until - time.time())

        return {
            "accounts": {
                "total": total,
                "success": success,
                "failed": failed,
                "pending": pending,
            },
            "workers": {
                "active": active_workers,
                "max": self.config.get_max_workers(),
            },
            "queue_size": self.task_queue.qsize(),
            "cooldown_remaining": round(cooldown_remaining),
            "consecutive_failures": self._consecutive_failures,
        }

    def stop_all(self):
        """Stop all tasks"""
        # Clear queue
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except:
                break

        # Mark all pending as failed
        with self.accounts_lock:
            for account in self.accounts.values():
                if account.status not in [AccountStatus.SUCCESS, AccountStatus.FAILED]:
                    account.status = AccountStatus.FAILED
                    account.error_message = "Stopped by user"

        self._save_accounts(force=True)
        logger.info("[AccountManager] Stopped all tasks")


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from config import Config
    from veteran_data import VeteranDataManager

    config = Config()
    vet_manager = VeteranDataManager()

    manager = AccountManager(config, vet_manager)

    print("\nSystem Status:")
    print(json.dumps(manager.get_status(), indent=2, ensure_ascii=False))
