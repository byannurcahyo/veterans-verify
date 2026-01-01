
import csv
import random
import datetime
from pathlib import Path

# Configuration
OUTPUT_FILE = "data/birls_update.csv"
RECORD_COUNT = 150

# Source Data for Random Generation
FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Donald", "Mark", "Paul", "Steven", "Andrew", "Kenneth",
    "George", "Joshua", "Kevin", "Brian", "Edward", "Ronald", "Timothy", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Stephen", "Jonathan", "Larry", "Justin", "Scott", "Brandon",
    "Frank", "Benjamin", "Gregory", "Samuel", "Raymond", "Patrick", "Alexander", "Jack", "Dennis", "Jerry"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
]

BRANCHES = ["ARMY", "NAVY", "AIR FORCE", "MARINE CORPS", "COAST GUARD"]

def generate_random_dob(start_year=1980, end_year=2003):
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + datetime.timedelta(days=random_number_of_days)
    return random_date.strftime("%Y-%m-%d")

def generate_synthetic_data():
    print(f"Generating {RECORD_COUNT} synthetic veteran records...")
    
    header = ["dob", "first", "last", "branch_1"]
    
    # Ensure data dir exists
    Path("data").mkdir(exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        
        for _ in range(RECORD_COUNT):
            dob = generate_random_dob()
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            branch = random.choice(BRANCHES)
            
            writer.writerow([dob, first, last, branch])
            
    print(f"Successfully generated {RECORD_COUNT} records to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_synthetic_data()
