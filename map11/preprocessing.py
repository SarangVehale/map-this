import concurrent.futures
import time
import threading
import requests
import pandas as pd
import sqlite3

# Constants
RATE_LIMIT = 1.5  # Initial retry wait time (in seconds)
MAX_PARALLEL_REQUESTS = 5  # Reduce parallel requests to avoid hitting limits too quickly
RETRY_LIMIT = 5  # Number of retries for failed requests
DB_FILE = "geocoding_cache.db"
LIMIT = 1  # Limit the number of results returned by the API

# Semaphore to control the number of parallel requests
semaphore = threading.Semaphore(MAX_PARALLEL_REQUESTS)

# Function to create the database table if it doesn't exist
def create_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS geocoded_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_query TEXT UNIQUE,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        geocoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()
    print("Table 'geocoded_locations' created or already exists.")

# Function to check the database for cached results
def get_cached_lat_long(location_query):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT latitude, longitude FROM geocoded_locations WHERE location_query = ?", (location_query,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (None, None)

# Function to save geocoded results to the database
def cache_lat_long(location_query, latitude, longitude):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO geocoded_locations (location_query, latitude, longitude)
    VALUES (?, ?, ?)
    """, (location_query, latitude, longitude))
    conn.commit()
    conn.close()

# Function to handle retry logic with exponential backoff and manual throttling
def geocode_location_with_retry(location_query, retries=RETRY_LIMIT):
    for attempt in range(retries):
        lat, lng = get_cached_lat_long(location_query)
        if lat is not None and lng is not None:
            return lat, lng

        # Make the API call if not cached
        url = f"https://nominatim.openstreetmap.org/search?q={location_query}&format=json&limit={LIMIT}"
        headers = {"User-Agent": "MyGeocodingApp/1.0 (myemail@example.com)"}
        try:
            with semaphore:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data:
                    lat = float(data[0]['lat'])
                    lng = float(data[0]['lon'])
                    cache_lat_long(location_query, lat, lng)
                    return lat, lng
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limiting
                wait_time = RATE_LIMIT * (2 ** attempt)  # Exponential backoff
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Error geocoding '{location_query}': {e}")
        except Exception as e:
            print(f"Unexpected error for '{location_query}': {e}")

    return None, None  # Return None if all retries failed

# Function to preprocess the data
def preprocess_data(input_file, output_file):
    data = pd.read_csv(input_file)

    # Clean up and prepare the location query string
    data['location_query'] = (
        data['Police Station'].fillna('') + ", " +
        data['District'].fillna('') + ", " +
        data['State/UT Name'].fillna('') + ", India"
    )

    latitudes = []
    longitudes = []

    # Process location queries in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        # Process each location query in parallel with retry logic
        results = list(executor.map(geocode_location_with_retry, data['location_query']))

    # Collect results
    for lat, lng in results:
        latitudes.append(lat)
        longitudes.append(lng)

    # Add latitudes and longitudes to dataframe
    data['latitude'] = latitudes
    data['longitude'] = longitudes

    # Save the updated dataframe to CSV
    data.to_csv(output_file, index=False)
    print(f"Preprocessing complete. Output saved to '{output_file}'.")

# Main execution
if __name__ == "__main__":
    # Ensure the geocoded_locations table exists
    create_table()

    input_csv = "/home/i4c/Documents/map-this/map8/crime_data.csv"  # Input file path
    output_csv = "complaints_with_lat_long.csv"  # Output file path
    preprocess_data(input_csv, output_csv)

