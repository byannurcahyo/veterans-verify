"""
Veterans Verify - Veteran Data Management
Based on BIRLS database real public information
"""
import csv
import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# SheerID supported branches
SHEERID_BRANCHES = [
    "Air Force",
    "Army",
    "Coast Guard",
    "Marine Corps",
    "Navy",
    "Space Force"
]

# BIRLS database branch mapping
BRANCH_MAPPING = {
    # Air Force related
    "AIR FORCE": "Air Force",
    "AF": "Air Force",
    "USAF": "Air Force",
    "ANG": "Air Force",  # Air National Guard
    "AIR NATIONAL GUARD": "Air Force",

    # Army related
    "ARMY": "Army",
    "A": "Army",
    "USA": "Army",
    "ARNG": "Army",  # Army National Guard
    "ARMY NATIONAL GUARD": "Army",
    "NG": "Army",  # National Guard (default Army)

    # Coast Guard
    "COAST GUARD": "Coast Guard",
    "CG": "Coast Guard",
    "USCG": "Coast Guard",

    # Marine Corps
    "MARINE CORPS": "Marine Corps",
    "MARINES": "Marine Corps",
    "M": "Marine Corps",
    "MC": "Marine Corps",
    "USMC": "Marine Corps",

    # Navy
    "NAVY": "Navy",
    "N": "Navy",
    "USN": "Navy",

    # Space Force (newer, might not be in BIRLS)
    "SPACE FORCE": "Space Force",
    "SF": "Space Force",
    "USSF": "Space Force",
}


class VeteranDataManager:
    """Veteran Data Manager"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.birls_csv = self.data_dir / "birls_update.csv"
        self.processed_json = self.data_dir / "veterans_processed.json"
        self.used_json = self.data_dir / "veterans_used.json"

        self.veterans: List[Dict] = []
        self.used_ids: set = set()

        self._load_data()

    def _load_data(self):
        """Load data"""
        # Load processed data
        if self.processed_json.exists():
            with open(self.processed_json, 'r', encoding='utf-8') as f:
                self.veterans = json.load(f)
            logger.info(f"Loaded {len(self.veterans)} processed records")

        # Load used records
        if self.used_json.exists():
            with open(self.used_json, 'r', encoding='utf-8') as f:
                self.used_ids = set(json.load(f))
            logger.info(f"Loaded {len(self.used_ids)} used records")

    def _save_used(self):
        """Save used records"""
        with open(self.used_json, 'w', encoding='utf-8') as f:
            json.dump(list(self.used_ids), f)

    def _normalize_branch(self, branch_raw: str) -> Optional[str]:
        """Map BIRLS branch code to SheerID format"""
        branch_upper = branch_raw.upper().strip()
        return BRANCH_MAPPING.get(branch_upper)

    def process_birls_csv(self, min_birth_year: int = 1980, max_birth_year: int = 2005):
        """
        Process BIRLS CSV file, filter matching records

        Conditions:
        1. Birth year between min_birth_year ~ max_birth_year
        2. Complete name (first + last)
        3. Recognizable branch
        """
        if not self.birls_csv.exists():
            logger.error(f"BIRLS CSV file not found: {self.birls_csv}")
            return 0

        logger.info(f"Start processing BIRLS CSV: {self.birls_csv}")

        valid_records = []
        seen_keys = set()  # Deduplication

        with open(self.birls_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse DOB
                dob = row.get('dob', '').strip()
                if not dob or '-' not in dob:
                    continue

                try:
                    birth_year = int(dob.split('-')[0])
                except ValueError:
                    continue

                if not (min_birth_year <= birth_year <= max_birth_year):
                    continue

                # Parse name
                first_name = row.get('first', '').strip().title()
                last_name = row.get('last', '').strip().title()

                if not first_name or not last_name:
                    continue

                # Parse branch
                branch_raw = row.get('branch_1', '').strip()
                branch = self._normalize_branch(branch_raw)

                if not branch:
                    continue

                # Create unique key for deduplication
                unique_key = f"{first_name}_{last_name}_{dob}"
                if unique_key in seen_keys:
                    continue
                seen_keys.add(unique_key)

                # Parse birth date to dictionary format
                dob_parts = dob.split('-')
                birth_date = {
                    "year": dob_parts[0],
                    "month": self._month_num_to_name(int(dob_parts[1])),
                    "day": str(int(dob_parts[2]))  # Remove leading zero
                }

                valid_records.append({
                    "id": unique_key,
                    "first_name": first_name,
                    "last_name": last_name,
                    "birth_date": birth_date,
                    "branch": branch,
                    "source": "BIRLS"
                })

        # Save processed data
        self.veterans = valid_records
        with open(self.processed_json, 'w', encoding='utf-8') as f:
            json.dump(valid_records, f, indent=2, ensure_ascii=False)

        logger.info(f"Processing completed, {len(valid_records)} valid records")
        return len(valid_records)

    @staticmethod
    def _month_num_to_name(month_num: int) -> str:
        """Month number to name"""
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        return months[month_num - 1] if 1 <= month_num <= 12 else "January"

    def get_random_veteran(self) -> Optional[Dict]:
        """
        Get a random unused veteran info

        Return format:
        {
            "first_name": "John",
            "last_name": "Smith",
            "birth_date": {"month": "March", "day": "15", "year": "1985"},
            "branch": "Army",
            "discharge_date": {"month": "August", "day": "20", "year": "2024"}  # Randomly generated
        }
        """
        if not self.veterans:
            logger.error("No available veteran data, please run process_birls_csv() first")
            return None

        # Filter unused records
        available = [v for v in self.veterans if v["id"] not in self.used_ids]

        if not available:
            logger.warning("All records used, resetting used records")
            self.used_ids.clear()
            self._save_used()
            available = self.veterans

        # Random selection
        veteran = random.choice(available)

        # Mark as used
        self.used_ids.add(veteran["id"])
        self._save_used()

        # Generate random discharge date (past 1-11 months)
        discharge_date = self._generate_random_discharge_date()

        return {
            "first_name": veteran["first_name"],
            "last_name": veteran["last_name"],
            "birth_date": veteran["birth_date"],
            "branch": veteran["branch"],
            "discharge_date": discharge_date
        }

    def _generate_random_discharge_date(self) -> Dict[str, str]:
        """
        Generate random discharge date (within past 1-11 months)

        SheerID requires discharge date to be within past 12 months
        """
        today = datetime.now()

        # Random 1-11 months ago
        months_ago = random.randint(1, 11)

        # Calculate date
        discharge_date = today - timedelta(days=months_ago * 30 + random.randint(0, 25))

        return {
            "month": self._month_num_to_name(discharge_date.month),
            "day": str(discharge_date.day),
            "year": str(discharge_date.year)
        }

    def get_stats(self) -> Dict:
        """Get data statistics"""
        return {
            "total": len(self.veterans),
            "used": len(self.used_ids),
            "available": len(self.veterans) - len(self.used_ids),
            "branches": self._count_by_branch()
        }

    def _count_by_branch(self) -> Dict[str, int]:
        """Count by branch"""
        counts = {}
        for v in self.veterans:
            branch = v.get("branch", "Unknown")
            counts[branch] = counts.get(branch, 0) + 1
        return counts


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = VeteranDataManager()

    # If data not processed, process first
    if not manager.veterans:
        print("Processing BIRLS data...")
        count = manager.process_birls_csv()
        print(f"Processing complete: {count} records")

    # Statistics
    stats = manager.get_stats()
    print(f"\nData Statistics:")
    print(f"  Total: {stats['total']}")
    print(f"  Used: {stats['used']}")
    print(f"  Available: {stats['available']}")
    print(f"\nDistribution by Branch:")
    for branch, count in sorted(stats['branches'].items(), key=lambda x: -x[1]):
        print(f"  {branch}: {count}")

    # Get random records
    print(f"\nGet 3 random records:")
    for i in range(3):
        vet = manager.get_random_veteran()
        if vet:
            print(f"  {i+1}. {vet['first_name']} {vet['last_name']}")
            print(f"     DOB: {vet['birth_date']['month']} {vet['birth_date']['day']}, {vet['birth_date']['year']}")
            print(f"     Branch: {vet['branch']}")
            print(f"     Discharge: {vet['discharge_date']['month']} {vet['discharge_date']['day']}, {vet['discharge_date']['year']}")
