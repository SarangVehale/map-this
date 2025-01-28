import folium
from folium.plugins import MarkerCluster
import pandas as pd
import json
import streamlit as st
from folium import IFrame
from streamlit_folium import folium_static

def create_crime_rate_map(filtered_data, map_center, zoom_start=5):
    """
    Create an interactive map based on filtered data.
    """
    # Create a base map centered on the selected region
    india_map = folium.Map(location=map_center, zoom_start=zoom_start)

    # Create marker cluster for police stations
    marker_cluster = MarkerCluster(name="Police Stations").add_to(india_map)

    for _, row in filtered_data.iterrows():
        lat = row['Latitude']
        lon = row['Longitude']
        police_station_name = row['Police Station']
        crime_count = row['Crime Count']  # Ensure this exists in the filtered data
        iframe = IFrame(f"<b>Police Station: {police_station_name}</b><br>Total Crimes: {crime_count}", width=200, height=100)
        folium.Marker([lat, lon], popup=folium.Popup(iframe)).add_to(marker_cluster)

    # Add layer control to toggle between different layers
    folium.LayerControl().add_to(india_map)

    return india_map

def main():
    # Load data
    states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_STATES.geojson"
    crime_data_csv_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/crime_data.csv"
    police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_POLICE_STATIONS.geojson"

    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)

    crime_data = pd.read_csv(crime_data_csv_path)

    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)

    # Extract police station coordinates
    police_station_coords = {}
    for feature in police_stations_data['features']:
        properties = feature['properties']
        coordinates = feature['geometry']['coordinates']
        key = (properties['state'], properties['district'], properties['ps'])
        police_station_coords[key] = (coordinates[1], coordinates[0])  # Latitude, Longitude

    # Add latitude and longitude to the crime data
    crime_data['Latitude'] = None
    crime_data['Longitude'] = None

    for index, row in crime_data.iterrows():
        state = row['State/UT Name']
        district = row['District']
        police_station = row['Police Station']

        key = (state, district, police_station)
        if key in police_station_coords:
            crime_data.at[index, 'Latitude'], crime_data.at[index, 'Longitude'] = police_station_coords[key]

    # Calculate crime count for each police station (this will be the 'Crime Count' column)
    crime_data['Crime Count'] = crime_data.groupby(['State/UT Name', 'District', 'Police Station'])['Police Station'].transform('count')

    # Get a list of unique states for the dropdown
    states = crime_data['State/UT Name'].unique()

    # Streamlit UI setup
    st.title("Interactive Crime Rate Map")

    # State dropdown
    selected_state = st.selectbox("Select State", states)

    # Filter the crime data based on selected state
    filtered_state_data = crime_data[crime_data['State/UT Name'] == selected_state]
    
    # Get unique districts in the selected state
    districts = filtered_state_data['District'].unique()

    # District dropdown (dynamic based on selected state)
    selected_district = st.selectbox("Select District", districts)

    # Filter the data based on selected district
    filtered_district_data = filtered_state_data[filtered_state_data['District'] == selected_district]
    
    # Get unique police stations in the selected district
    police_stations = filtered_district_data['Police Station'].unique()

    # Police station dropdown (dynamic based on selected district)
    selected_police_station = st.selectbox("Select Police Station", police_stations)

    # Filter the data based on selected police station
    filtered_police_station_data = filtered_district_data[filtered_district_data['Police Station'] == selected_police_station]

    # Set map center to the selected region (district or police station)
    if len(filtered_police_station_data) > 0:
        map_center = [filtered_police_station_data['Latitude'].mean(), filtered_police_station_data['Longitude'].mean()]
    else:
        map_center = [filtered_district_data['Latitude'].mean(), filtered_district_data['Longitude'].mean()]

    # Create map with filtered data
    crime_map = create_crime_rate_map(filtered_police_station_data, map_center)

    # Display map in Streamlit
    folium_static(crime_map)

if __name__ == "__main__":
    main()

