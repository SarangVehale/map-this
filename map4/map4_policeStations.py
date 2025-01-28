import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


def geocode_location(state, police_station):
    """Geocode a location using geopy."""
    geolocator = Nominatim(user_agent="geo_locator")
    try:
        location = geolocator.geocode(f"{police_station}, {state}, India", timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            print(f"Could not find location: {police_station}, {state}")
            return None, None
    except GeocoderTimedOut:
        print(f"Geocoding timed out for: {police_station}, {state}")
        return None, None


def mark_locations_on_map(file_path, state_col="State", station_col="Police Station"):
    """Read an Excel file, geocode locations, and create a map with markers."""
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)

        # Check if required columns are present
        if state_col not in df.columns or station_col not in df.columns:
            print(f"Columns '{state_col}' and/or '{station_col}' not found in the file.")
            return

        # Filter rows where either State or Police Station is missing
        df = df.dropna(subset=[state_col, station_col])

        # Initialize the map
        map_center = [20.5937, 78.9629]  # Centered at India's geographical center
        m = folium.Map(location=map_center, zoom_start=5)

        # Geocode each row and add markers
        for _, row in df.iterrows():
            state = row[state_col]
            police_station = row[station_col]
            lat, long = geocode_location(state, police_station)
            if lat and long:
                folium.Marker(
                    location=[lat, long],
                    popup=f"Police Station: {police_station}<br>State: {state}",
                    tooltip=f"{police_station}, {state}",
                ).add_to(m)

        # Save the map to an HTML file
        output_file = "police_stations_map.html"
        m.save(output_file)
        print(f"Map saved as '{output_file}'. Open this file in a browser to view the map.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Example usage
    input_file = input("Enter the path to the Excel file: ")
    mark_locations_on_map(input_file)

