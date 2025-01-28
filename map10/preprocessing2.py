import configparser
import pandas as pd
import aiohttp
import asyncio
import sqlite3
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    filename='geocoding.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

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
    logging.info("Table 'geocoded_locations' created or already exists.")

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

# Asynchronous function to geocode a location using OpenCage API
async def geocode_location(session, location_query):
    # Skip empty location queries
    if not location_query.strip():
        logging.warning(f"Skipping empty location query.")
        return None, None, False

    # Check cache first
    lat, lng = get_cached_lat_long(location_query)
    if lat is not None and lng is not None:
        logging.info(f"Cache hit for: {location_query} -> ({lat}, {lng})")
        return lat, lng, True  # Indicating a successful geocode

    # Make API call if not cached
    url = f"https://api.opencagedata.com/geocode/v1/json?q={location_query}&key={API_KEY}"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()

            if data['results']:
                lat = data['results'][0]['geometry']['lat']
                lng = data['results'][0]['geometry']['lng']
                logging.info(f"Geocoded: {location_query} -> ({lat}, {lng})")
                # Cache the result
                cache_lat_long(location_query, lat, lng)
                return lat, lng, True  # Indicating a successful geocode
            else:
                logging.warning(f"No results for: {location_query}")
    except Exception as e:
        logging.error(f"Error geocoding '{location_query}': {e}")

    return None, None, False  # Indicating a failed geocode

# Function to preprocess the data using asyncio for faster geocoding
async def preprocess_data(input_file, output_file):
    # Load the CSV file
    data = pd.read_csv(input_file)

    # Create a combined location query string
    data['location_query'] = (
        data['Police Station'].fillna('') + ", " +
        data['District'].fillna('') + ", " +
        data['State/UT Name'].fillna('') + ", India"
    )

    # Filter out rows with empty location queries
    data = data[data['location_query'].str.strip() != '']

    # Prepare the list of queries to process
    queries = data['location_query'].tolist()

    # Counters for successful and failed geocoding
    successful = 0
    failed = 0

    # Use asyncio to process multiple geocoding requests concurrently
    async with aiohttp.ClientSession() as session:
        tasks = []
        for query in tqdm(queries, desc="Geocoding locations", unit="query"):
            task = asyncio.ensure_future(geocode_location(session, query))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

    # Add lat-long columns to the dataframe
    latitudes = []
    longitudes = []

    for result in results:
        lat, lng, success = result
        if success:
            successful += 1
        else:
            failed += 1
        latitudes.append(lat)
        longitudes.append(lng)

    data['latitude'] = latitudes
    data['longitude'] = longitudes

    # Calculate the success rate
    success_rate = (successful / (successful + failed)) * 100

    # Save the updated CSV
    data.to_csv(output_file, index=False)

    # Logging the results
    logging.info(f"Geocoding complete!")
    logging.info(f"Successfully geocoded: {successful}")
    logging.info(f"Failed to geocode: {failed}")
    logging.info(f"Success rate: {success_rate:.2f}%")

    # Printing the final summary
    print(f"Geocoding complete!")
    print(f"Successfully geocoded: {successful}")
    print(f"Failed to geocode: {failed}")
    print(f"Success rate: {success_rate:.2f}%")

# Main execution
if __name__ == "__main__":
    try:
        print("Processing CSV file...")
        # Ensure the geocoded_locations table exists
        create_table()

        input_csv = "/home/i4c/Documents/map-this/map8/crime_data.csv"  # Input file path
        output_csv = "complaints_with_lat_long.csv"  # Output file path

        # Run the async preprocessing function
        asyncio.run(preprocess_data(input_csv, output_csv))

    except Exception as e:
        logging.critical(f"Critical error during execution: {e}")

