import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any

# Use Streamlit's caching for better performance
@st.cache_data
def load_data(states_geojson_path: str, crime_data_csv_path: str, police_stations_geojson_path: str) -> Tuple[Dict, pd.DataFrame, Dict]:
    """
    Load and cache the required data files.
    
    Args:
        states_geojson_path: Path to states GeoJSON file
        crime_data_csv_path: Path to crime data CSV file
        police_stations_geojson_path: Path to police stations GeoJSON file
        
    Returns:
        Tuple containing states GeoJSON, crime data DataFrame, and police stations data
    """
    try:
        with open(states_geojson_path, 'r', encoding='utf-8') as f:
            states_geojson = json.load(f)

        crime_data = pd.read_csv(crime_data_csv_path)
        # Convert District column to string to ensure consistent sorting
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
    """
    Match crime data with police station coordinates.
    
    Args:
        crime_data: DataFrame containing crime data
        police_stations_data: Dictionary containing police station GeoJSON data
        
    Returns:
        Tuple of updated DataFrame and list of unmatched entries
    """
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
    """
    Approximate missing location data using district or state centroids.
    
    Args:
        crime_data: DataFrame containing crime data
        
    Returns:
        Updated DataFrame with approximated locations
    """
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
    crime_data: pd.DataFrame,
    selected_state: str,
    selected_district: str,
    selected_police_station: str
) -> folium.Map:
    """
    Create an interactive crime rate map with filters.
    
    Args:
        states_geojson: GeoJSON data for states
        crime_data: DataFrame containing crime data
        selected_state: Selected state filter
        selected_district: Selected district filter
        selected_police_station: Selected police station filter
        
    Returns:
        Folium map object
    """
    # Initialize map centered on India
    india_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    # Add state boundaries with styling
    folium.GeoJson(
        states_geojson,
        style_function=lambda x: {
            'fillColor': '#ffaf00',
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0.3
        }
    ).add_to(india_map)

    # Filter data based on selections
    filtered_data = crime_data.copy()
    if selected_state != "All States":
        filtered_data = filtered_data[filtered_data['State/UT Name'] == selected_state]
    if selected_district != "All Districts":
        filtered_data = filtered_data[filtered_data['District'] == selected_district]
    if selected_police_station != "All Police Stations":
        filtered_data = filtered_data[filtered_data['Police Station'] == selected_police_station]

    # Create marker cluster for better performance with many points
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

    return india_map

def main():
    """Main application function."""
    # Configure the page
    st.set_page_config(
        page_title="Interactive Crime Rate Map",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Header
    st.title("Interactive Crime Rate Map")
    st.markdown("---")

    try:

        # Load data
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_STATES.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_POLICE_STATIONS.geojson"
        # Load data paths (replace with your actual paths)
        #states_geojson_path = "data/INDIA_STATES.geojson"
        #crime_data_csv_path = "data/crime_data.csv"
        #police_stations_geojson_path = "data/INDIA_POLICE_STATIONS.geojson"

        # Validate file existence
        for file_path in [states_geojson_path, crime_data_csv_path, police_stations_geojson_path]:
            if not os.path.exists(file_path):
                st.error(f"File not found: {file_path}")
                return

        # Load and process data
        states_geojson, crime_data, police_stations_data = load_data(
            states_geojson_path,
            crime_data_csv_path,
            police_stations_geojson_path
        )

        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

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

                # District filter - ensure all values are strings before sorting
                district_data = crime_data[crime_data['State/UT Name'] == selected_state] if selected_state != "All States" else crime_data
                district_options = ["All Districts"] + sorted(district_data['District'].astype(str).unique().tolist())
                selected_district = st.selectbox(
                    "Select District",
                    district_options,
                    help="Filter crime data by district"
                )

                # Police Station filter - ensure all values are strings before sorting
                station_data = district_data[district_data['District'] == selected_district] if selected_district != "All Districts" else district_data
                station_options = ["All Police Stations"] + sorted(station_data['Police Station'].astype(str).unique().tolist())
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
