import pandas as pd
import sqlite3
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.extra.rate_limiter import RateLimiter
import time
from tqdm import tqdm
import hashlib
import requests
import json
import backoff
import concurrent.futures
import logging
import threading
from contextlib import contextmanager
from queue import Queue

# Set up logging
logging.basicConfig(
    filename='geocoding.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DatabaseConnectionPool:
    def __init__(self, database_path):
        self.database_path = database_path
        self.local = threading.local()
        
    @contextmanager
    def get_connection(self):
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.database_path)
        try:
            yield self.local.connection
        except Exception as e:
            self.local.connection.rollback()
            raise e

class GeocodingService:
    def __init__(self):
        self.nominatim = RateLimiter(
            Nominatim(user_agent="crime_map_preprocessor").geocode,
            min_delay_seconds=1.5,
            max_retries=3,
            error_wait_seconds=2.0
        )
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'crime_map_preprocessor'
        })

    @backoff.on_exception(
        backoff.expo,
        (GeocoderTimedOut, GeocoderUnavailable, requests.exceptions.RequestException),
        max_tries=5
    )
    def geocode(self, location_string):
        try:
            location = self.nominatim(location_string)
            if location:
                return location.latitude, location.longitude
            return None, None
        except Exception as e:
            logging.error(f"Error geocoding {location_string}: {str(e)}")
            return None, None

def create_location_database():
    """Create SQLite database for storing geocoded locations"""
    conn = sqlite3.connect('locations.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (location_hash TEXT PRIMARY KEY,
                  location_string TEXT,
                  latitude REAL,
                  longitude REAL,
                  attempts INTEGER DEFAULT 0,
                  last_attempt DATETIME,
                  success BOOLEAN,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_location_hash ON locations(location_hash)')
    conn.commit()
    conn.close()
    
    return DatabaseConnectionPool('locations.db')

def get_location_hash(location_string):
    """Create a unique hash for a location string"""
    return hashlib.md5(location_string.encode()).hexdigest()

def process_location(args):
    """Process a single location with the geocoding service"""
    location_string, geocoding_service, db_pool = args
    location_hash = get_location_hash(location_string)
    
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        
        # Check if location exists and was successfully geocoded
        c.execute("""
            SELECT latitude, longitude 
            FROM locations 
            WHERE location_hash = ? AND success = 1
        """, (location_hash,))
        result = c.fetchone()
        
        if result:
            return True
        
        # Attempt geocoding
        lat, lon = geocoding_service.geocode(location_string)
        success = lat is not None and lon is not None
        
        # Update database
        c.execute("""
            INSERT OR REPLACE INTO locations 
            (location_hash, location_string, latitude, longitude, attempts, last_attempt, success)
            VALUES (?, ?, ?, ?, 
                    COALESCE((SELECT attempts + 1 FROM locations WHERE location_hash = ?), 1),
                    CURRENT_TIMESTAMP,
                    ?)
        """, (location_hash, location_string, lat, lon, location_hash, success))
        
        conn.commit()
        return success

def process_batch(locations, db_pool, geocoding_service, progress_queue):
    """Process a batch of locations"""
    for location in locations:
        success = process_location((location, geocoding_service, db_pool))
        progress_queue.put(1)  # Report progress

def preprocess_locations(csv_file, max_workers=4, batch_size=100):
    """Preprocess all locations from the CSV file with parallel processing"""
    print("Reading CSV file...")
    df = pd.read_csv(csv_file)
    
    # Create database connection pool
    db_pool = create_location_database()
    geocoding_service = GeocodingService()
    
    print("Extracting unique locations...")
    locations = set()
    
    # Process state-level locations
    states = df['State/UT Name'].dropna().unique()
    for state in states:
        locations.add(f"{state}, India")
    
    # Process district-level locations
    districts = df.dropna(subset=['District', 'State/UT Name'])[['District', 'State/UT Name']].drop_duplicates()
    for _, row in districts.iterrows():
        locations.add(f"{row['District']}, {row['State/UT Name']}, India")
    
    # Process police station-level locations
    stations = df.dropna(subset=['Police Station', 'District', 'State/UT Name'])[
        ['Police Station', 'District', 'State/UT Name']
    ].drop_duplicates()
    for _, row in stations.iterrows():
        locations.add(f"{row['Police Station']}, {row['District']}, {row['State/UT Name']}, India")
    
    locations = list(locations)
    total_locations = len(locations)
    print(f"Found {total_locations} unique locations to process")
    
    # Create progress queue and progress bar
    progress_queue = Queue()
    pbar = tqdm(total=total_locations, desc="Geocoding locations")
    
    # Split locations into batches
    batches = [locations[i:i + batch_size] for i in range(0, len(locations), batch_size)]
    
    # Process batches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batches
        futures = [
            executor.submit(process_batch, batch, db_pool, geocoding_service, progress_queue)
            for batch in batches
        ]
        
        # Update progress bar
        completed = 0
        while completed < total_locations:
            progress_queue.get()
            completed += 1
            pbar.update(1)
    
    pbar.close()
    
    # Print statistics
    with db_pool.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM locations WHERE success = 1")
        successful = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM locations WHERE success = 0")
        failed = c.fetchone()[0]
    
    print("\nPreprocessing complete!")
    print(f"Successfully geocoded: {successful}")
    print(f"Failed to geocode: {failed}")
    print(f"Success rate: {(successful/(successful+failed)*100):.2f}%")
    print(f"Database location: locations.db")
    print(f"Check geocoding.log for detailed error messages")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Preprocess location data for crime mapping')
    parser.add_argument('--csv', default='crime_data.csv', help='Input CSV file')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    args = parser.parse_args()
    
    preprocess_locations(args.csv, args.workers, args.batch_size)
