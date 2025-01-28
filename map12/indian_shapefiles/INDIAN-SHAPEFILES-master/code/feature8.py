import folium
from folium.plugins import MarkerCluster
from folium.features import GeoJson
import pandas as pd
import json
import streamlit as st
from streamlit_folium import st_folium  # Correct import for st_folium
from time import sleep

# Use Streamlit's new caching for data operations
@st.cache_data
def load_data(states_geojson_path, crime_data_csv_path, police_stations_geojson_path):
    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)

    crime_data = pd.read_csv(crime_data_csv_path)

    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)

    return states_geojson, crime_data, police_stations_data

# Function to create the crime rate map
def create_crime_rate_map(states_geojson, crime_data, police_stations_data, selected_state, selected_district, selected_police_station):
    """
    Create an interactive map to visualize crime rates with dropdown filters.
    """
    india_map = folium.Map(location=[22.0, 78.0], zoom_start=5)

    # Zoom and highlight selected region
    if selected_state != "All States":
        state_data = states_geojson['features']
        state_feature = next((feature for feature in state_data if feature['properties']['STNAME'] == selected_state), None)
        if state_feature:
            # Check if centroid is a single point or a multi-point geometry
            centroid = state_feature['geometry']['coordinates']
            
            if isinstance(centroid[0][0], list):  # Multi-polygon geometry (state with multiple boundaries)
                # Calculate the centroid of the multipolygon
                centroid_lat = sum([point[1] for point in centroid[0][0]]) / len(centroid[0][0])
                centroid_lon = sum([point[0] for point in centroid[0][0]]) / len(centroid[0][0])
            else:  # Single-point centroid
                centroid_lat = centroid[1]
                centroid_lon = centroid[0]

            india_map.location = [centroid_lat, centroid_lon]
            india_map.zoom_start = 6

            # Highlight state boundaries
            GeoJson(state_feature, name="State Boundary",
                    style_function=lambda x: {'fillColor': '#ffaf00', 'color': 'black', 'weight': 2, 'fillOpacity': 0.3}).add_to(india_map)

    # Add crime rate markers
    def add_crime_rate_marker(location, crime_count, label):
        if location:
            folium.CircleMarker(
                location=location,
                radius=5 + (crime_count / 10),  # Adjust radius based on crime count
                color='blue',
                fill=True,
                fill_color='blue',
                fill_opacity=0.6,
                popup=f"{label}<br>Total Crimes: {crime_count}"
            ).add_to(india_map)

    # Add state-level crime rate markers
    state_counts = crime_data.groupby('State/UT Name').size().reset_index(name='Crime Count')
    for _, row in state_counts.iterrows():
        state_name = row['State/UT Name']
        crime_count = row['Crime Count']
        state_data = crime_data[crime_data['State/UT Name'] == state_name]
        
        # Ensure Latitude and Longitude columns exist, handle missing
        if 'Latitude' in state_data.columns and 'Longitude' in state_data.columns:
            centroid_lat = state_data['Latitude'].mean()
            centroid_lon = state_data['Longitude'].mean()
        else:
            # Fallback: use the centroid calculation logic for the state
            centroid_lat = 22.0  # Default to center of India if data is missing
            centroid_lon = 78.0
        
        add_crime_rate_marker([centroid_lat, centroid_lon], crime_count, f"State: {state_name}")

    # Add district-level crime rate markers
    district_counts = crime_data.groupby(['State/UT Name', 'District']).size().reset_index(name='Crime Count')
    for _, row in district_counts.iterrows():
        district_name = row['District']
        crime_count = row['Crime Count']
        district_data = crime_data[crime_data['District'] == district_name]
        
        # Ensure Latitude and Longitude columns exist, handle missing
        if 'Latitude' in district_data.columns and 'Longitude' in district_data.columns:
            centroid_lat = district_data['Latitude'].mean()
            centroid_lon = district_data['Longitude'].mean()
        else:
            centroid_lat = 22.0  # Fallback
            centroid_lon = 78.0
        
        add_crime_rate_marker([centroid_lat, centroid_lon], crime_count, f"District: {district_name}")

    # Add police station-level crime rate markers using MarkerCluster
    police_station_counts = crime_data.groupby(['State/UT Name', 'District', 'Police Station']).size().reset_index(name='Crime Count')
    marker_cluster = MarkerCluster(name="Police Stations").add_to(india_map)
    for _, row in police_station_counts.iterrows():
        police_station_name = row['Police Station']
        crime_count = row['Crime Count']
        station_data = crime_data[crime_data['Police Station'] == police_station_name]
        
        # Ensure Latitude and Longitude columns exist, handle missing
        if 'Latitude' in station_data.columns and 'Longitude' in station_data.columns:
            station_lat = station_data['Latitude'].mean()
            station_lon = station_data['Longitude'].mean()
        else:
            station_lat = 22.0  # Fallback
            station_lon = 78.0
        
        if not pd.isna(station_lat) and not pd.isna(station_lon):
            folium.Marker(
                location=[station_lat, station_lon],
                popup=folium.Popup(f"<b>Police Station: {police_station_name}</b><br>Total Crimes: {crime_count}"),
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(marker_cluster)

    return india_map

# Main Streamlit interface
def main():
    st.title("Interactive Crime Rate Map")

     # Load data
    states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_STATES.geojson"
    crime_data_csv_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/crime_data.csv"
    police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_POLICE_STATIONS.geojson"
    states_geojson, crime_data, police_stations_data = load_data(states_geojson_path, crime_data_csv_path, police_stations_geojson_path)

    # Show a loading spinner
    with st.spinner('Loading data...'):
        sleep(2)  # Simulate some loading time

    # Create a container for the navbar (filter section) and the map
    filters = st.container()
    with filters:
        st.markdown("""
            <style>
                .sidebar .sidebar-content {
                    padding-top: 0px;
                }
                .st-bq {
                    padding-top: 10px;
                }
            </style>
            """, unsafe_allow_html=True)

        # Create a horizontal navbar for filters using columns
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            # Dropdown for state selection
            state_options = ["All States"] + list(crime_data['State/UT Name'].unique())
            selected_state = st.selectbox("Select State", state_options)

        with col2:
            # Dynamically update district options based on selected state
            if selected_state != "All States":
                district_options = ["All Districts"] + list(crime_data[crime_data['State/UT Name'] == selected_state]['District'].unique())
            else:
                district_options = ["All Districts"]
            selected_district = st.selectbox("Select District", district_options)

        with col3:
            # Dynamically update police station options based on selected district
            if selected_state != "All States" and selected_district != "All Districts":
                police_station_options = ["All Police Stations"] + list(crime_data[(crime_data['State/UT Name'] == selected_state) & (crime_data['District'] == selected_district)]['Police Station'].unique())
            else:
                police_station_options = ["All Police Stations"]
            selected_police_station = st.selectbox("Select Police Station", police_station_options)

    # Create the map with selected filters
    crime_map = create_crime_rate_map(states_geojson, crime_data, police_stations_data, selected_state, selected_district, selected_police_station)

    # Display the map in Streamlit using st_folium in full screen
    st_folium(crime_map, width=1500)

if __name__ == "__main__":
    main()

