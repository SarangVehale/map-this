import folium
from folium.plugins import MarkerCluster
import pandas as pd
import sqlite3

# Load the geocoded data
def load_data(database_path="geocoding_cache.db"):
    """
    Load geocoded data from an SQLite database.

    Args:
        database_path (str): Path to the SQLite database.

    Returns:
        pd.DataFrame: Geocoded data as a DataFrame.
    """
    conn = sqlite3.connect(database_path)
    try:
        # Check if the table exists
        query_check = "SELECT name FROM sqlite_master WHERE type='table' AND name='geocoded_locations';"
        table_exists = not pd.read_sql_query(query_check, conn).empty

        if table_exists:
            query = "SELECT * FROM geocoded_locations"
            df = pd.read_sql_query(query, conn)
            print("Loaded data successfully.")
        else:
            print("No data found in the database.")
            df = pd.DataFrame()  # Return empty DataFrame if no data exists
    except Exception as e:
        print(f"Error while loading data: {e}")
        raise
    finally:
        conn.close()
    return df

# Aggregate crime data by levels (state, district, police station)
def aggregate_crime_data(data):
    """
    Aggregate crime data at different levels.

    Args:
        data (pd.DataFrame): Geocoded data.

    Returns:
        tuple: Aggregated data at state, district, and station levels.
    """
    state_data = data.groupby("state")["crime_count"].sum().reset_index()
    district_data = data.groupby(["state", "district"])["crime_count"].sum().reset_index()
    station_data = data.groupby(["state", "district", "police_station"])["crime_count"].sum().reset_index()
    return state_data, district_data, station_data

# Add markers based on zoom level
def add_markers(map_obj, data, zoom_level, original_data=None):
    """
    Add markers to a Folium map.

    Args:
        map_obj (folium.Map): Map object to add markers.
        data (pd.DataFrame): Aggregated data for markers (state, district, station).
        zoom_level (str): Level of aggregation ('state', 'district', 'station').
        original_data (pd.DataFrame): Original data with latitude and longitude.
    """
    if zoom_level == "state":
        # Use original data for latitude/longitude
        for _, row in original_data.iterrows():
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    popup=f"State: {row['state']}<br>Crimes: {row['crime_count']}",
                    icon=folium.Icon(color="blue", icon="info-sign"),
                ).add_to(map_obj)
    elif zoom_level == "district":
        for _, row in data.iterrows():
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    popup=f"District: {row['district']}<br>Crimes: {row['crime_count']}",
                    icon=folium.Icon(color="green", icon="info-sign"),
                ).add_to(map_obj)
    elif zoom_level == "station":
        for _, row in data.iterrows():
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    popup=f"Station: {row['police_station']}<br>Crimes: {row['crime_count']}",
                    icon=folium.Icon(color="red", icon="info-sign"),
                ).add_to(map_obj)

# Initialize the map
def create_crime_map(data, original_data):
    """
    Create a crime map using Folium.

    Args:
        data (pd.DataFrame): Aggregated data.
        original_data (pd.DataFrame): Original data with latitude and longitude.

    Returns:
        folium.Map: Crime map.
    """
    map_center = [21.7679, 78.8718]  # Center of India
    crime_map = folium.Map(location=map_center, zoom_start=5, tiles="OpenStreetMap")

    # Cluster for better visualization
    marker_cluster = MarkerCluster().add_to(crime_map)

    # Get aggregated data
    state_data, district_data, station_data = aggregate_crime_data(data)

    # Add state-level markers (using the original data)
    add_markers(marker_cluster, state_data, zoom_level="state", original_data=original_data)

    # Add zoom level behavior
    folium.LayerControl().add_to(crime_map)

    return crime_map

# Main execution
def main():
    """
    Main function to load data, create the crime map, and save it as an HTML file.
    """
    # Load the geocoded data
    data = load_data()

    # Ensure required columns exist in the data
    if "latitude" not in data.columns or "longitude" not in data.columns:
        raise ValueError("Data must contain 'latitude' and 'longitude' columns.")
    if "crime_count" not in data.columns:
        data["crime_count"] = 1  # Default crime count if not available

    # If no data is available, exit gracefully
    if data.empty:
        print("No data available to create the map. Exiting.")
        return

    # Create the crime map
    crime_map = create_crime_map(data, original_data=data)

    # Save the map to an HTML file
    crime_map.save("crime_map.html")
    print("Crime map created and saved as crime_map.html")

if __name__ == "__main__":
    main()

