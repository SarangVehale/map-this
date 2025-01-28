import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from rapidfuzz import process
import json
import time

# Hardcoded paths for GeoJSON files
STATE_GEOJSON = "/home/i4c/Documents/map-this/data/india.geojson"
DISTRICT_GEOJSON = "/home/i4c/Documents/map-this/data/INDIA_DISTRICTS.geojson"

def standardize_name(name):
    """Standardize location names for matching."""
    if pd.isnull(name):
        return ""
    return name.strip().upper().replace('&', 'AND').replace(',', '')

def find_best_match(name, geojson_names, threshold=85):
    """Find the best match using fuzzy matching."""
    match, score = process.extractOne(name, geojson_names)
    return match if score >= threshold else None

def geocode_location(state, district, police_station):
    """Geocode a location using geopy."""
    geolocator = Nominatim(user_agent="geo_locator")
    try:
        location = geolocator.geocode(f"{police_station}, {district}, {state}, India", timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            print(f"Could not find location: {police_station}, {district}, {state}")
            return None, None
    except GeocoderTimedOut:
        print(f"Geocoding timed out for: {police_station}, {district}, {state}")
        return None, None

def find_column(columns, target):
    """Find a column by partial or case-insensitive match."""
    for col in columns:
        if target.lower() in col.lower():
            return col
    return None

def extract_geojson_key(geojson_path, level="state"):
    """Extract the key for state or district names dynamically from a GeoJSON file."""
    with open(geojson_path, 'r') as f:
        geojson = json.load(f)
        properties = geojson['features'][0]['properties']
        print(f"{level.capitalize()} GeoJSON properties:", properties)
        for key in properties.keys():
            print(f" - {key}")
        selected_key = input(f"Enter the key for {level} name (e.g., state name for {level} level): ")
        return selected_key

def create_crime_map(file_path):
    """Create a map showing crime data at multiple levels."""
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        print("Columns in the file:", df.columns.tolist())
        df.columns = df.columns.str.strip()

        # Match column names dynamically
        state_col = find_column(df.columns, "State/UT name")
        district_col = find_column(df.columns, "District")
        station_col = find_column(df.columns, "Police Station")
        category_col = find_column(df.columns, "Category")
        sub_category_col = find_column(df.columns, "Sub Category")

        if not all([state_col, district_col, station_col, category_col, sub_category_col]):
            print("One or more required columns were not found.")
            print("Available columns:", df.columns.tolist())
            return

        # Standardize and match district names
        with open(DISTRICT_GEOJSON, 'r') as f:
            geojson = json.load(f)
            geojson_districts = [standardize_name(feature['properties']['dtname']) for feature in geojson['features']]
        df['District_Standardized'] = df[district_col].apply(standardize_name)
        df['Matched_District'] = df['District_Standardized'].apply(
            lambda x: find_best_match(x, geojson_districts)
        )

        # Check for unmatched locations
        unmatched = df[df['Matched_District'].isnull()]
        if not unmatched.empty:
            print("Unmatched Districts:")
            print(unmatched[[district_col, 'District_Standardized']])

        # Aggregate data at different levels
        df['Matched_District'] = df['Matched_District'].fillna("Unknown")
        state_data = df.groupby(state_col).size().reset_index(name="Crime Count")
        district_data = df.groupby([state_col, 'Matched_District']).size().reset_index(name="Crime Count")
        station_data = df.groupby([state_col, 'Matched_District', station_col]).size().reset_index(name="Crime Count")

        # Initialize the map
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

        # Extract GeoJSON keys dynamically
        state_key = extract_geojson_key(STATE_GEOJSON, level="state")
        district_key = extract_geojson_key(DISTRICT_GEOJSON, level="district")

        # Add state-level data as a choropleth
        folium.Choropleth(
            geo_data=STATE_GEOJSON,
            data=state_data,
            columns=[state_col, "Crime Count"],
            key_on=f"feature.properties.{state_key}",
            fill_color="YlOrRd",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Total Crimes by State",
            name="State-Level Crimes",
        ).add_to(m)

        # Add district-level data as a choropleth
        folium.Choropleth(
            geo_data=DISTRICT_GEOJSON,
            data=district_data,
            columns=['Matched_District', "Crime Count"],
            key_on=f"feature.properties.{district_key}",
            fill_color="PuRd",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Total Crimes by District",
            name="District-Level Crimes",
        ).add_to(m)

        # Add police station-level markers
        for _, row in station_data.iterrows():
            state = row[state_col]
            district = row['Matched_District']
            station = row[station_col]
            num_crimes = row["Crime Count"]

            lat, lon = geocode_location(state, district, station)
            if lat and lon:
                folium.Marker(
                    location=[lat, lon],
                    popup=f"<b>Police Station:</b> {station}<br>"
                          f"<b>District:</b> {district}<br>"
                          f"<b>State:</b> {state}<br>"
                          f"<b>Crimes:</b> {num_crimes}",
                    tooltip=f"{station} - Crimes: {num_crimes}",
                    icon=folium.Icon(color="red", icon="info-sign"),
                ).add_to(m)
            time.sleep(1)  # Avoid overwhelming the geocoding service

        folium.LayerControl().add_to(m)
        output_file = "multi_level_crime_map.html"
        m.save(output_file)
        print(f"Map saved as '{output_file}'.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    csv_file = input("Enter the path to the CSV file: ")
    create_crime_map(csv_file)

