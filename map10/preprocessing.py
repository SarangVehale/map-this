import configparser
import pandas as pd
import requests
import sqlite3
import time

# Function to read the API key from the config file
def get_api_key():
    config = configparser.ConfigParser()
    config.read('config.ini')
    api_key = config.get('api', 'opencage_api_key')
    return api_key

# Constants
API_KEY = get_api_key()

if not API_KEY:
    raise ValueError("API key is missing. Please set the opencage_api_key in the config file.")

RATE_LIMIT = 1.5  # Time (in seconds) between API calls to respect rate limits

# SQLite database file
DB_FILE = "geocoding_cache.db"

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

# Function to geocode a location using OpenCage API
def geocode_location(location_query):
    # Check cache first
    lat, lng = get_cached_lat_long(location_query)
    if lat is not None and lng is not None:
        return lat, lng
    
    # Make API call if not cached
    url = f"https://api.opencagedata.com/geocode/v1/json?q={location_query}&key={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            lat = data['results'][0]['geometry']['lat']
            lng = data['results'][0]['geometry']['lng']
            # Cache the result
            cache_lat_long(location_query, lat, lng)
            return lat, lng
    except Exception as e:
        print(f"Error geocoding '{location_query}': {e}")
    
    return None, None

# Function to preprocess the data
def preprocess_data(input_file, output_file):
    # Load the CSV file
    data = pd.read_csv(input_file)
    
    # Create a combined location query string
    data['location_query'] = (
        data['Police Station'].fillna('') + ", " +
        data['District'].fillna('') + ", " +
        data['State/UT Name'].fillna('') + ", India"
    )
    
    # Geocode each location and store lat-long
    latitudes = []
    longitudes = []
    for i, query in enumerate(data['location_query']):
        print(f"Processing {i + 1}/{len(data)}: {query}")
        lat, lng = geocode_location(query)
        latitudes.append(lat)
        longitudes.append(lng)
        time.sleep(RATE_LIMIT)  # Respect API rate limits
    
    # Add lat-long columns to the dataframe
    data['latitude'] = latitudes
    data['longitude'] = longitudes
    
    # Save the updated CSV
    data.to_csv(output_file, index=False)
    print(f"Preprocessing complete. Output saved to '{output_file}'.")

# Main execution
if __name__ == "__main__":
    # Ensure the geocoded_locations table exists
    create_table()
    
    input_csv = "/home/i4c/Documents/map-this/map8/crime_data.csv"  # Input file path
    output_csv = "complaints_with_lat_long.csv"  # Output file path
    preprocess_data(input_csv, output_csv)

