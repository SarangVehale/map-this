import folium
from folium.plugins import MarkerCluster
from folium.features import GeoJson
import pandas as pd
import json
import streamlit as st
from streamlit_folium import st_folium  # Correct import for st_folium

# Use Streamlit's new caching for data operations
@st.cache_data
def load_data(states_geojson_path, crime_data_csv_path, police_stations_geojson_path):
    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)

    crime_data = pd.read_csv(crime_data_csv_path)

    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)

    return states_geojson, crime_data, police_stations_data

# Cache the crime data matching process to avoid redundant computation
@st.cache_data
def match_coordinates(crime_data, police_stations_data):
    police_station_coords = {}
    for feature in police_stations_data['features']:
        properties = feature['properties']
        coordinates = feature['geometry']['coordinates']
        key = (properties['state'], properties['district'], properties['ps'])
        police_station_coords[key] = (coordinates[1], coordinates[0])  # Latitude, Longitude

    unmatched_entries = []
    crime_data['Latitude'] = None
    crime_data['Longitude'] = None

    for index, row in crime_data.iterrows():
        state = row['State/UT Name']
        district = row['District']
        police_station = row['Police Station']

        key = (state, district, police_station)
        if key in police_station_coords:
            crime_data.at[index, 'Latitude'], crime_data.at[index, 'Longitude'] = police_station_coords[key]
        else:
            unmatched_entries.append(f"Unmatched: {state} - {district} - {police_station}")

    return crime_data, unmatched_entries

# Cache approximate missing location calculation to avoid repeated computation
@st.cache_data
def approximate_missing_locations(crime_data):
    for index, row in crime_data.iterrows():
        if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
            state = row['State/UT Name']
            district = row['District']

            # Calculate the district centroid if available
            district_data = crime_data[(crime_data['State/UT Name'] == state) & (crime_data['District'] == district)]
            if not district_data[['Latitude', 'Longitude']].dropna().empty:
                crime_data.at[index, 'Latitude'] = district_data['Latitude'].mean()
                crime_data.at[index, 'Longitude'] = district_data['Longitude'].mean()
            else:
                # Fallback to state centroid
                state_data = crime_data[crime_data['State/UT Name'] == state]
                if not state_data[['Latitude', 'Longitude']].dropna().empty:
                    crime_data.at[index, 'Latitude'] = state_data['Latitude'].mean()
                    crime_data.at[index, 'Longitude'] = state_data['Longitude'].mean()

    return crime_data

# Function to create the crime rate map
def create_crime_rate_map(states_geojson, crime_data, police_stations_data, selected_state, selected_district, selected_police_station):
    """
    Create an interactive map to visualize crime rates with dropdown filters.
    """

    # Filter data based on selections
    filtered_data = crime_data
    if selected_state != "All States":
        filtered_data = filtered_data[filtered_data['State/UT Name'] == selected_state]
    if selected_district != "All Districts":
        filtered_data = filtered_data[filtered_data['District'] == selected_district]
    if selected_police_station != "All Police Stations":
        filtered_data = filtered_data[filtered_data['Police Station'] == selected_police_station]

    # Create base map and default zoom level
    india_map = folium.Map(location=[22.0, 78.0], zoom_start=5)

    # Initialize map view based on selection
    if selected_state != "All States":
        state_data = states_geojson['features']
        state_feature = next((feature for feature in state_data if feature['properties']['STNAME'] == selected_state), None)
        if state_feature:
            centroid = state_feature['geometry']['coordinates'][0][0]
            centroid_lat = sum([point[1] for point in centroid]) / len(centroid)
            centroid_lon = sum([point[0] for point in centroid]) / len(centroid)
            india_map.location = [centroid_lat, centroid_lon]
            india_map.zoom_start = 6  # Zoom into the state

            # Highlight state boundaries
            GeoJson(state_feature, name="State Boundary",
                    style_function=lambda x: {'fillColor': '#ffaf00', 'color': 'black', 'weight': 2, 'fillOpacity': 0.3}).add_to(india_map)

    if selected_district != "All Districts":
        district_data = filtered_data[filtered_data['District'] == selected_district]
        centroid_lat = district_data['Latitude'].mean()
        centroid_lon = district_data['Longitude'].mean()
        india_map.location = [centroid_lat, centroid_lon]
        india_map.zoom_start = 7  # Zoom into the district

        # Highlight district boundaries (you can further refine this logic based on your dataset)
        folium.CircleMarker([centroid_lat, centroid_lon], radius=10, color="red", fill=True, fill_color="red").add_to(india_map)

    if selected_police_station != "All Police Stations":
        station_data = filtered_data[filtered_data['Police Station'] == selected_police_station]
        station_lat = station_data['Latitude'].mean()
        station_lon = station_data['Longitude'].mean()
        india_map.location = [station_lat, station_lon]
        india_map.zoom_start = 8  # Zoom into the police station

        # Highlight police station (use the same technique as for district)
        folium.Marker([station_lat, station_lon], popup=f"Police Station: {selected_police_station}").add_to(india_map)

    # Function to safely add markers or circles
    def add_marker_or_circle(location, popup, radius=0, color="blue", fill=True, fill_color="blue", fill_opacity=0.6):
        if location and not pd.isna(location[0]) and not pd.isna(location[1]):
            if radius > 0:
                folium.CircleMarker(
                    location=location,
                    radius=radius,
                    color=color,
                    fill=fill,
                    fill_color=fill_color,
                    fill_opacity=fill_opacity,
                    popup=popup,
                ).add_to(india_map)
            else:
                folium.Marker(
                    location=location,
                    popup=popup,
                    icon=folium.Icon(color="blue", icon="info-sign"),
                ).add_to(india_map)

    # Add markers based on filtered data
    state_counts = filtered_data.groupby('State/UT Name').size().reset_index(name='Crime Count')
    for _, row in state_counts.iterrows():
        state_name = row['State/UT Name']
        crime_count = row['Crime Count']
        state_data = filtered_data[filtered_data['State/UT Name'] == state_name]
        centroid_lat = state_data['Latitude'].mean()
        centroid_lon = state_data['Longitude'].mean()

        add_marker_or_circle([centroid_lat, centroid_lon], f"<b>{state_name}</b><br>Total Crimes: {crime_count}", radius=min(20, crime_count / 10), color="red", fill_color="red")

    # Add district-level circle markers
    district_counts = filtered_data.groupby(['State/UT Name', 'District']).size().reset_index(name='Crime Count')
    for _, row in district_counts.iterrows():
        district_name = row['District']
        crime_count = row['Crime Count']
        district_data = filtered_data[filtered_data['District'] == district_name]
        centroid_lat = district_data['Latitude'].mean()
        centroid_lon = district_data['Longitude'].mean()

        add_marker_or_circle([centroid_lat, centroid_lon], f"<b>{district_name}</b><br>Total Crimes: {crime_count}", radius=min(15, crime_count / 5), color="orange", fill_color="orange")

    # Add police station-level markers using MarkerCluster
    police_station_counts = filtered_data.groupby(['State/UT Name', 'District', 'Police Station']).size().reset_index(name='Crime Count')
    marker_cluster = MarkerCluster(name="Police Stations").add_to(india_map)
    for _, row in police_station_counts.iterrows():
        police_station_name = row['Police Station']
        crime_count = row['Crime Count']
        station_data = filtered_data[filtered_data['Police Station'] == police_station_name]
        station_lat = station_data['Latitude'].mean()
        station_lon = station_data['Longitude'].mean()

        if not pd.isna(station_lat) and not pd.isna(station_lon):
            folium.Marker(
                location=[station_lat, station_lon],
                popup=folium.Popup(f"<b>Police Station: {police_station_name}</b><br>Total Crimes: {crime_count}"),
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(marker_cluster)

    # Add layer control for interactivity
    folium.LayerControl().add_to(india_map)

    return india_map

# Main Streamlit interface
def main():
    st.title("Interactive Crime Rate Map")

    # Load data
    states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_STATES.geojson"
    crime_data_csv_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/crime_data.csv"
    police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_POLICE_STATIONS.geojson"
    states_geojson, crime_data, police_stations_data = load_data(states_geojson_path, crime_data_csv_path, police_stations_geojson_path)

    # Match coordinates and approximate missing data
    crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
    crime_data = approximate_missing_locations(crime_data)

    # Sidebar for filters
    st.sidebar.title("Filters")
    state_options = ["All States"] + list(crime_data['State/UT Name'].unique())
    selected_state = st.sidebar.selectbox("Select State", state_options)

    # Dynamically update district options based on selected state
    if selected_state != "All States":
        district_options = ["All Districts"] + list(crime_data[crime_data['State/UT Name'] == selected_state]['District'].unique())
    else:
        district_options = ["All Districts"]
    selected_district = st.sidebar.selectbox("Select District", district_options)

    # Dynamically update police station options based on selected district
    if selected_state != "All States" and selected_district != "All Districts":
        police_station_options = ["All Police Stations"] + list(crime_data[(crime_data['State/UT Name'] == selected_state) & (crime_data['District'] == selected_district)]['Police Station'].unique())
    else:
        police_station_options = ["All Police Stations"]
    selected_police_station = st.sidebar.selectbox("Select Police Station", police_station_options)

    # Create the map with selected filters
    crime_map = create_crime_rate_map(states_geojson, crime_data, police_stations_data, selected_state, selected_district, selected_police_station)

    # Display the map in Streamlit using st_folium
    st_folium(crime_map, width=1080)

if __name__ == "__main__":
    main()

