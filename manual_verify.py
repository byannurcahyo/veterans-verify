"""
Veterans Verify - Manual Verification Tool
Allows semi-automated verification steps:
1. Submit SheerID Form (using specific Link + Email + Random Veteran Data)
2. Verify Email Token (using specific Link)
"""
import asyncio
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from browser_worker import BrowserWorker, VerifyTask
from veteran_data import VeteranDataManager

async def main():
    print("\n============================================")
    print("   Veterans Verify - Manual Tool")
    print("============================================")
    print("1. Submit SheerID Form (Link + Email)")
    print("2. Verify Email Token (Link with token)")
    print("3. Generate SheerID Link (JWT)")
    print("4. Exit")
    
    choice = input("\nSelect Option (1-4): ").strip()
    
    if choice == "1":
        await handle_submit_form()
    elif choice == "2":
        await handle_verify_token()
    elif choice == "3":
        await handle_generate_link()
    elif choice == "4":
        print("Exiting...")
        return
    else:
        print("Invalid choice")

async def handle_submit_form():
    """Handle Option 1: Submit Form"""
    print("\n--- Submit SheerID Form ---")
    print("Please enter the SheerID Verification URL:")
    print("Example: https://services.sheerid.com/verify/...?verificationId=...")
    sheerid_url = input("URL: ").strip()
    
    if not sheerid_url:
        print("Error: URL is required")
        return

    print("\nPlease enter the Email to use:")
    email = input("Email: ").strip()
    
    if not email or "@" not in email:
        print("Error: Valid email is required")
        return

    print("\nInitializing Veteran Data...")
    vet_manager = VeteranDataManager()
    vet_data = vet_manager.get_random_veteran()
    
    if not vet_data:
        print("Error: Could not load veteran data")
        return

    print(f"\nUsing Random Veteran Data:")
    print(f"  Name: {vet_data['first_name']} {vet_data['last_name']}")
    print(f"  Branch: {vet_data['branch']}")
    print(f"  DOB: {vet_data['birth_date']}")
    
    print("\nStarting Browser Worker...")
    worker = BrowserWorker(headless=False, screenshot_dir="screenshots")
    
    # Create a task object just for data holding
    task = VerifyTask(
        task_id=f"manual-{email.split('@')[0]}",
        email=email,
        first_name=vet_data["first_name"],
        last_name=vet_data["last_name"],
        branch=vet_data["branch"],
        birth_date=vet_data["birth_date"],
        discharge_date=vet_data["discharge_date"]
    )
    
    success = await worker.run_manual_sheerid_form(task, sheerid_url)
    
    if success:
        print("\n✅ SUCCESS: Verification form submitted (or already verified).")
        print("Please check your email for the verification link.")
    else:
        print("\n❌ FAILED: Could not complete form submission.")
        
    print("Closing application...")

async def handle_verify_token():
    """Handle Option 2: Verify Token"""
    print("\n--- Verify Email Token ---")
    print("Please enter the Verification Link from email:")
    print("Example: ...&emailToken=123456")
    verify_url = input("URL: ").strip()
    
    if not verify_url:
        print("Error: URL is required")
        return

    print("\nStarting Browser Worker...")
    worker = BrowserWorker(headless=False, screenshot_dir="screenshots")
    
    success = await worker.run_email_token_verification(verify_url)
    
    if success:
        print("\n✅ SUCCESS: Account Verification Completed!")
    else:
        print("\n❌ FAILED: Verification failed or timed out.")

    print("Closing application...")

async def handle_generate_link():
    """Handle Option 3: Generate Link from JWT"""
    print("\n--- Generate SheerID Link (JWT) ---")
    print("Please enter ChatGPT JWT Token:")
    jwt_token = input("JWT: ").strip()
    
    if not jwt_token:
        print("Error: JWT is required")
        return

    print("\nStarting Browser Worker...")
    worker = BrowserWorker(headless=False, screenshot_dir="screenshots")
    
    link = await worker.get_sheerid_link_from_jwt(jwt_token)
    
    if link:
        print(f"\n✅ SUCCESS: Generated SheerID Link:")
        print(f"{link}")
    else:
        print("\n❌ FAILED: Could not generate link.")

    print("Closing application...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled by user")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
