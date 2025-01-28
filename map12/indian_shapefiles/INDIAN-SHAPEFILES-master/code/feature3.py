import folium
from folium.plugins import MarkerCluster
import pandas as pd
import json

def create_crime_rate_map(states_geojson_path, crime_data_csv_path, police_stations_geojson_path, output_file="crime_rate_map.html", log_file="unmatched_entries.log"):
    """
    Create an interactive hierarchical map to visualize crime rates.
    Also log unmatched entries to a log file.

    Args:
        states_geojson_path (str): Path to GeoJSON file for states boundaries.
        crime_data_csv_path (str): Path to CSV file with crime data.
        police_stations_geojson_path (str): Path to GeoJSON file with police station data.
        output_file (str): Path to save the generated HTML map.
        log_file (str): Path to save the log file for unmatched entries.
    """
    # Load the GeoJSON data for states
    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)

    # Load the crime data from CSV
    crime_data = pd.read_csv(crime_data_csv_path)

    # Load the police station data from GeoJSON
    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)

    # Extract the police stations and their coordinates
    police_station_coords = {}
    for feature in police_stations_data['features']:
        properties = feature['properties']
        coordinates = feature['geometry']['coordinates']
        key = (properties['state'], properties['district'], properties['ps'])
        police_station_coords[key] = (coordinates[1], coordinates[0])  # Latitude, Longitude

    # Add latitude and longitude to the crime data based on matching state, district, and police station name
    unmatched_entries = []
    crime_data['Latitude'] = None
    crime_data['Longitude'] = None

    for index, row in crime_data.iterrows():
        state = row['State/UT Name']
        district = row['District']
        police_station = row['Police Station']
        
        # Look for a match in the police station coordinates dictionary
        key = (state, district, police_station)
        if key in police_station_coords:
            crime_data.at[index, 'Latitude'], crime_data.at[index, 'Longitude'] = police_station_coords[key]
        else:
            unmatched_entries.append(f"Unmatched: {state} - {district} - {police_station}")
            # Add the crime to the district or state-level crime
            crime_data.at[index, 'Latitude'], crime_data.at[index, 'Longitude'] = None, None  # Leave as NaN to not plot
            # Log the unmatched entry with a tag "Unknown police station"
            crime_data.at[index, 'Crime Reported'] = f"Unknown Police Station Crime Report ({state}, {district})"
    
    # Log unmatched entries to a file
    with open(log_file, 'w') as log:
        for entry in unmatched_entries:
            log.write(entry + '\n')

    # Remove rows where Latitude or Longitude are missing (NaN)
    crime_data = crime_data.dropna(subset=['Latitude', 'Longitude'])

    # Group by state to get the total number of crimes per state
    state_counts = crime_data.groupby('State/UT Name').size().reset_index(name='Crime Count')

    # Group by district to get the total number of crimes per district
    district_counts = crime_data.groupby(['State/UT Name', 'District']).size().reset_index(name='Crime Count')

    # Group by police station to get the total number of crimes per police station
    police_station_counts = crime_data.groupby(['State/UT Name', 'District', 'Police Station']).size().reset_index(name='Crime Count')

    # Create a base map centered on India
    india_map = folium.Map(location=[22.0, 78.0], zoom_start=5)

    # Add state-level circle markers for crime rates
    for _, row in state_counts.iterrows():
        state_name = row['State/UT Name']
        crime_count = row['Crime Count']
        # Get state centroid (average lat/lon of police stations in this state)
        state_data = crime_data[crime_data['State/UT Name'] == state_name]
        centroid_lat = state_data['Latitude'].mean()
        centroid_lon = state_data['Longitude'].mean()

        # Add a proportional circle marker for the state
        folium.CircleMarker(
            location=[centroid_lat, centroid_lon],
            radius=min(20, crime_count / 10),  # Radius scaled by crime count
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.6,
            popup=folium.Popup(f"State: {state_name}<br>Total Crimes: {crime_count}"),
        ).add_to(india_map)

    # Add district-level circles and markers
    for _, row in district_counts.iterrows():
        state_name = row['State/UT Name']
        district_name = row['District']
        crime_count = row['Crime Count']
        # Get district centroid
        district_data = crime_data[(crime_data['State/UT Name'] == state_name) & (crime_data['District'] == district_name)]
        centroid_lat = district_data['Latitude'].mean()
        centroid_lon = district_data['Longitude'].mean()

        # Add a district-level circle marker
        folium.CircleMarker(
            location=[centroid_lat, centroid_lon],
            radius=min(15, crime_count / 5),  # Smaller scale for districts
            color="orange",
            fill=True,
            fill_color="orange",
            fill_opacity=0.6,
            popup=folium.Popup(f"District: {district_name}<br>Crimes: {crime_count}"),
        ).add_to(india_map)

    # Add police station-level markers using MarkerCluster
    marker_cluster = MarkerCluster(name="Police Stations").add_to(india_map)
    for _, row in police_station_counts.iterrows():
        state_name = row['State/UT Name']
        district_name = row['District']
        police_station_name = row['Police Station']
        crime_count = row['Crime Count']
        # Get police station latitude and longitude
        station_data = crime_data[
            (crime_data['State/UT Name'] == state_name) & 
            (crime_data['District'] == district_name) & 
            (crime_data['Police Station'] == police_station_name)
        ]
        station_lat = station_data['Latitude'].mean()
        station_lon = station_data['Longitude'].mean()

        # Add a marker for each police station
        folium.Marker(
            location=[station_lat, station_lon],
            popup=folium.Popup(f"Police Station: {police_station_name}<br>Crimes: {crime_count}"),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(marker_cluster)

    # Add layer control for interactivity
    folium.LayerControl().add_to(india_map)

    # Save the map to an HTML file
    india_map.save(output_file)
    print(f"Crime rate map has been saved to {output_file}. Open it in a web browser to view.")

# Example usage
states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_STATES.geojson"
crime_data_csv_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/crime_data.csv"
police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_POLICE_STATIONS.geojson"

create_crime_rate_map(states_geojson_path, crime_data_csv_path, police_stations_geojson_path)

