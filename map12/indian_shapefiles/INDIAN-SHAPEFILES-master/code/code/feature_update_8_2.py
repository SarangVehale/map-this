import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any

@st.cache_data
def load_data(states_geojson_path: str, crime_data_csv_path: str, police_stations_geojson_path: str) -> Tuple[Dict, pd.DataFrame, Dict]:
    """Load and cache the required data files."""
    try:
        with open(states_geojson_path, 'r', encoding='utf-8') as f:
            states_geojson = json.load(f)

        # Load crime data and convert relevant columns to string
        crime_data = pd.read_csv(crime_data_csv_path)
        crime_data['State/UT Name'] = crime_data['State/UT Name'].astype(str)
        crime_data['District'] = crime_data['District'].astype(str)
        crime_data['Police Station'] = crime_data['Police Station'].astype(str)

        with open(police_stations_geojson_path, 'r', encoding='utf-8') as f:
            police_stations_data = json.load(f)

        return states_geojson, crime_data, police_stations_data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        raise

@st.cache_data
def match_coordinates(crime_data: pd.DataFrame, police_stations_data: Dict) -> Tuple[pd.DataFrame, List[str]]:
    """Match crime data with police station coordinates."""
    police_station_coords = {}
    for feature in police_stations_data['features']:
        try:
            properties = feature['properties']
            coordinates = feature['geometry']['coordinates']
            if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
                lat, lon = float(coordinates[1]), float(coordinates[0])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    key = (str(properties['state']), str(properties['district']), str(properties['ps']))
                    police_station_coords[key] = (lat, lon)
        except (KeyError, ValueError, TypeError):
            continue

    unmatched_entries = []
    crime_data['Latitude'] = pd.NA
    crime_data['Longitude'] = pd.NA

    for index, row in crime_data.iterrows():
        try:
            state = str(row['State/UT Name'])
            district = str(row['District'])
            police_station = str(row['Police Station'])

            key = (state, district, police_station)
            if key in police_station_coords:
                crime_data.at[index, 'Latitude'], crime_data.at[index, 'Longitude'] = police_station_coords[key]
            else:
                unmatched_entries.append(f"Unmatched: {state} - {district} - {police_station}")
        except Exception as e:
            unmatched_entries.append(f"Error processing row {index}: {str(e)}")

    return crime_data, unmatched_entries

@st.cache_data
def approximate_missing_locations(crime_data: pd.DataFrame) -> pd.DataFrame:
    """Approximate missing location data using district or state centroids."""
    for index, row in crime_data.iterrows():
        try:
            if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
                state = str(row['State/UT Name'])
                district = str(row['District'])

                # Try district centroid first
                district_data = crime_data[
                    (crime_data['State/UT Name'] == state) &
                    (crime_data['District'] == district)
                ]
                district_coords = district_data[['Latitude', 'Longitude']].dropna()

                if not district_coords.empty:
                    crime_data.at[index, 'Latitude'] = float(district_coords['Latitude'].mean())
                    crime_data.at[index, 'Longitude'] = float(district_coords['Longitude'].mean())
                else:
                    # Fallback to state centroid
                    state_data = crime_data[crime_data['State/UT Name'] == state]
                    state_coords = state_data[['Latitude', 'Longitude']].dropna()
                    if not state_coords.empty:
                        crime_data.at[index, 'Latitude'] = float(state_coords['Latitude'].mean())
                        crime_data.at[index, 'Longitude'] = float(state_coords['Longitude'].mean())
        except Exception:
            continue

    return crime_data

def create_crime_rate_map(
    states_geojson: Dict,
    districts_geojson: Dict,
    crime_data: pd.DataFrame,
    selected_state: str,
    selected_district: str,
    selected_police_station: str
) -> folium.Map:
    """Create an interactive crime rate map with filters and zooming."""
    # Initialize map centered on India
    india_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    # Function to get bounds from coordinates
    def get_bounds(data):
        if not data.empty and 'Latitude' in data.columns and 'Longitude' in data.columns:
            valid_coords = data[data['Latitude'].notna() & data['Longitude'].notna()]
            if not valid_coords.empty:
                min_lat = valid_coords['Latitude'].min()
                max_lat = valid_coords['Latitude'].max()
                min_lon = valid_coords['Longitude'].min()
                max_lon = valid_coords['Longitude'].max()
                return [[min_lat, min_lon], [max_lat, max_lon]]
        return None

    # Filter data based on selections
    filtered_data = crime_data.copy()
    highlight_state = None
    highlight_district = None

    if selected_state != "All States":
        filtered_data = filtered_data[filtered_data['State/UT Name'] == selected_state]
        # Find the state in GeoJSON to highlight
        for feature in states_geojson['features']:
            if feature['properties'].get('STNAME') == selected_state:
                highlight_state = feature
                break

    if selected_district != "All Districts":
        filtered_data = filtered_data[filtered_data['District'] == selected_district]
        # Find the district in GeoJSON to highlight
        if districts_geojson and selected_state != "All States":
            for feature in districts_geojson['features']:
                if (feature['properties'].get('dtname') == selected_district and 
                    feature['properties'].get('stname') == selected_state):
                    highlight_district = feature
                    break
    
    if selected_police_station != "All Police Stations":
        filtered_data = filtered_data[filtered_data['Police Station'] == selected_police_station]

    # Add appropriate boundaries with conditional styling
    def style_function(feature):
        default_style = {
            'fillColor': '#ffaf00',
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0.3
        }
        
        if highlight_district:
            # If district is selected, only highlight the specific district
            if (feature.get('properties', {}).get('dtname') == selected_district and 
                feature.get('properties', {}).get('stname') == selected_state):
                return {
                    'fillColor': '#ff6b6b',
                    'color': 'red',
                    'weight': 3,
                    'fillOpacity': 0.4
                }
            return {'fillOpacity': 0.1, 'weight': 1}
        elif highlight_state:
            # If only state is selected, highlight the entire state
            if feature.get('properties', {}).get('stname') == selected_state:
                return {
                    'fillColor': '#ff6b6b',
                    'color': 'red',
                    'weight': 3,
                    'fillOpacity': 0.4
                }
        return default_style

    # Add state boundaries
    folium.GeoJson(
        states_geojson,
        style_function=style_function,
        name="States"
    ).add_to(india_map)

    # Add district boundaries only if a specific state is selected
    if districts_geojson and selected_state != "All States":
        folium.GeoJson(
            districts_geojson,
            style_function=style_function,
            name="Districts"
        ).add_to(india_map)

    # Create marker cluster for better performance
    marker_cluster = MarkerCluster().add_to(india_map)

    # Add markers for crime locations
    for _, row in filtered_data.iterrows():
        try:
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                lat, lon = float(row['Latitude']), float(row['Longitude'])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    popup_html = f"""
                        <div style='font-family: Arial, sans-serif; padding: 10px;'>
                            <h4 style='margin: 0 0 10px 0;'>Location Details</h4>
                            <p><strong>State:</strong> {row['State/UT Name']}</p>
                            <p><strong>District:</strong> {row['District']}</p>
                            <p><strong>Police Station:</strong> {row['Police Station']}</p>
                        </div>
                    """
                    
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=8,
                        color='red',
                        fill=True,
                        fillColor='red',
                        fillOpacity=0.7,
                        popup=folium.Popup(popup_html, max_width=300)
                    ).add_to(marker_cluster)
        except Exception:
            continue

    # Adjust map bounds based on filtered data
    bounds = get_bounds(filtered_data)
    if bounds:
        india_map.fit_bounds(bounds)
    elif highlight_district:
        # If no points but district selected, zoom to district bounds
        coordinates = highlight_district['geometry']['coordinates']
        if isinstance(coordinates[0][0], list):  # Check if it's a Polygon
            coords = coordinates[0][0]
        else:  # Handle MultiPolygon or other structures
            coords = coordinates[0] if isinstance(coordinates[0], list) else coordinates

        if coords:
            bounds = [
                [min(p[1] for p in coords), min(p[0] for p in coords)],
                [max(p[1] for p in coords), max(p[0] for p in coords)]
            ]
            india_map.fit_bounds(bounds)
    elif highlight_state:
        # If no points but state selected, zoom to state bounds
        coordinates = highlight_state['geometry']['coordinates']
        if isinstance(coordinates[0][0], list):  # Check if it's a Polygon
            coords = coordinates[0][0]
        else:  # Handle MultiPolygon or other structures
            coords = coordinates[0] if isinstance(coordinates[0], list) else coordinates

        if coords:
            bounds = [
                [min(p[1] for p in coords), min(p[0] for p in coords)],
                [max(p[1] for p in coords), max(p[0] for p in coords)]
            ]
            india_map.fit_bounds(bounds)

    # Adjust zoom level based on selection
    if selected_police_station != "All Police Stations":
        india_map.zoom_start = 15
    elif selected_district != "All Districts":
        india_map.zoom_start = 10
    elif selected_state != "All States":
        india_map.zoom_start = 7

    return india_map

def main():
    """Main application function."""
    st.set_page_config(
        page_title="Interactive Crime Rate Map",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("Interactive Crime Rate Map")
    st.markdown("---")

    try:
        # Load data
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_STATES.geojson"
        districts_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_DISTRICTS.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_POLICE_STATIONS.geojson"

        # Validate file existence
        required_files = [states_geojson_path, crime_data_csv_path, police_stations_geojson_path]
        for file_path in required_files:
            if not os.path.exists(file_path):
                st.error(f"File not found: {file_path}")
                return

        # Load and process data
        states_geojson, crime_data, police_stations_data = load_data(
            states_geojson_path,
            crime_data_csv_path,
            police_stations_geojson_path
        )

        # Load districts GeoJSON if available
        districts_geojson = None
        if os.path.exists(districts_geojson_path):
            with open(districts_geojson_path, 'r', encoding='utf-8') as f:
                districts_geojson = json.load(f)

        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

        # Convert columns to string type before sorting
        crime_data['State/UT Name'] = crime_data['State/UT Name'].astype(str)
        crime_data['District'] = crime_data['District'].astype(str)
        crime_data['Police Station'] = crime_data['Police Station'].astype(str)

        # Sidebar filters
        with st.sidebar:
            st.header("Filter Options")
            
            with st.expander("Show/Hide Filters", expanded=True):
                # State filter
                state_options = ["All States"] + sorted(crime_data['State/UT Name'].unique().tolist())
                selected_state = st.selectbox(
                    "Select State",
                    state_options,
                    help="Filter crime data by state"
                )

                # District filter
                district_data = crime_data[crime_data['State/UT Name'] == selected_state] if selected_state != "All States" else crime_data
                district_options = ["All Districts"] + sorted(district_data['District'].unique().tolist())
                selected_district = st.selectbox(
                    "Select District",
                    district_options,
                    help="Filter crime data by district"
                )

                # Police Station filter
                station_data = district_data[district_data['District'] == selected_district] if selected_district != "All Districts" else district_data
                station_options = ["All Police Stations"] + sorted(station_data['Police Station'].unique().tolist())
                selected_police_station = st.selectbox(
                    "Select Police Station",
                    station_options,
                    help="Filter crime data by police station"
                )

                if st.button("Reset Filters", type="primary"):
                    st.experimental_rerun()

        # Create and display map
        crime_map = create_crime_rate_map(
            states_geojson,
            districts_geojson,
            crime_data,
            selected_state,
            selected_district,
            selected_police_station
        )

        # Display map
        st_folium(
            crime_map,
            width="100%",
            height=800,
            returned_objects=["last_active_drawing"]
        )

    except Exception as e:
        st.error("An error occurred while loading the application.")
        st.error(f"Error details: {str(e)}")
        if st.checkbox("Show detailed error"):
            st.exception(e)

if __name__ == "__main__":
    main()