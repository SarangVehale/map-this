import folium
from folium.plugins import MarkerCluster
import pandas as pd
import json

def create_crime_rate_map(states_geojson_path, crime_data_csv_path, police_stations_geojson_path, output_file="crime_rate_map.html", log_file="unmatched_entries.log"):
    """
    Create an interactive hierarchical map to visualize crime rates.
    Includes smoother hover effects for state and district boundaries.
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

    # Log unmatched entries to a file
    with open(log_file, 'w') as log:
        for entry in unmatched_entries:
            log.write(entry + '\n')

    # Create a base map centered on India
    india_map = folium.Map(location=[22.0, 78.0], zoom_start=5)

    # Add GeoJSON layer for states with hover effect
    folium.GeoJson(
        states_geojson,
        style_function=lambda feature: {
            'fillColor': 'lightblue',
            'color': 'black',
            'weight': 1.5,
            'fillOpacity': 0.4,
        },
        highlight_function=lambda feature: {
            'fillColor': 'yellow',
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['STNAME'],  # Correct field name for state name
            aliases=['State: '],
            localize=True,
        )
    ).add_to(india_map)

    # Add police station-level markers using MarkerCluster
    police_station_counts = crime_data.groupby(['State/UT Name', 'District', 'Police Station']).size().reset_index(name='Crime Count')
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

        if not pd.isna(station_lat) and not pd.isna(station_lon):
            folium.Marker(
                location=[station_lat, station_lon],
                popup=folium.Popup(
                    f"<b>Police Station: {police_station_name}</b><br>Total Crimes: {crime_count}"
                ),
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(marker_cluster)

    # Add layer control for interactivity
    folium.LayerControl().add_to(india_map)

    # Save the map to an HTML file
    india_map.save(output_file)
    print(f"Crime rate map has been saved to {output_file}. Open it in a web browser to view.")

# Example usage
states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_STATES.geojson"
# districts_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_DISTRICTS.geojson"
crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/crime_data.csv"
police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_POLICE_STATIONS.geojson"
# Load data paths
create_crime_rate_map(states_geojson_path, crime_data_csv_path, police_stations_geojson_path)

