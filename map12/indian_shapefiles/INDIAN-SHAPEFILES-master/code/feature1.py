import folium
from folium.plugins import MarkerCluster
import pandas as pd
import json

def create_hierarchical_map(states_geojson_path, police_stations_geojson_path, output_file="hierarchical_map.html"):
    """
    Create an interactive hierarchical map to visualize police stations.

    Args:
        states_geojson_path (str): Path to GeoJSON file for states boundaries.
        police_stations_geojson_path (str): Path to GeoJSON file with police station data. 
                                            The GeoJSON should contain 'State', 'District', 
                                            and coordinates.
        output_file (str): Path to save the generated HTML map.
    """
    # Load the GeoJSON data for states
    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)
    
    # Load the police station GeoJSON data
    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)
    
    # Convert GeoJSON police station data to a pandas DataFrame
    police_stations = []
    for feature in police_stations_data['features']:
        properties = feature['properties']
        coordinates = feature['geometry']['coordinates']
        police_stations.append({
            "State": properties.get('state', 'Unknown'),
            "District": properties.get('district', 'Unknown'),
            "Latitude": coordinates[1],
            "Longitude": coordinates[0],
            "Name": properties.get('ps', 'Unknown')  # Use 'ps' for the police station name
        })
    data = pd.DataFrame(police_stations)
    
    # Group by state and district to get counts
    state_counts = data.groupby('State').size().reset_index(name='Count')
    district_counts = data.groupby(['State', 'District']).size().reset_index(name='Count')
    
    # Create a base map centered on India
    india_map = folium.Map(location=[22.0, 78.0], zoom_start=5)
    
    # Add state-level circle markers
    for _, row in state_counts.iterrows():
        state_name = row['State']
        count = row['Count']
        # Get state centroid (average lat/lon of police stations in this state)
        state_data = data[data['State'] == state_name]
        centroid_lat = state_data['Latitude'].mean()
        centroid_lon = state_data['Longitude'].mean()
        
        # Add a proportional circle marker
        folium.CircleMarker(
            location=[centroid_lat, centroid_lon],
            radius=min(20, count / 10),  # Radius scaled by count
            color="blue",
            fill=True,
            fill_color="blue",
            fill_opacity=0.6,
            popup=folium.Popup(f"State: {state_name}<br>Police Stations: {count}"),
        ).add_to(india_map)
    
    # Add district-level circles and markers
    for _, row in district_counts.iterrows():
        state_name = row['State']
        district_name = row['District']
        count = row['Count']
        # Get district centroid
        district_data = data[(data['State'] == state_name) & (data['District'] == district_name)]
        centroid_lat = district_data['Latitude'].mean()
        centroid_lon = district_data['Longitude'].mean()
        
        # Add a district-level circle
        folium.CircleMarker(
            location=[centroid_lat, centroid_lon],
            radius=min(15, count / 5),  # Smaller scale for districts
            color="green",
            fill=True,
            fill_color="green",
            fill_opacity=0.6,
            popup=folium.Popup(f"District: {district_name}<br>Police Stations: {count}"),
        ).add_to(india_map)
    
    # Add police station-level markers using MarkerCluster
    marker_cluster = MarkerCluster(name="Police Stations").add_to(india_map)
    for _, row in data.iterrows():
        # Update the popup to show the Name of the police station
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=folium.Popup(f"Police Station: {row['Name']}<br>District: {row['District']}<br>State: {row['State']}"),
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(marker_cluster)
    
    # Add layer control for interactivity
    folium.LayerControl().add_to(india_map)
    
    # Save the map to an HTML file
    india_map.save(output_file)
    print(f"Hierarchical map has been saved to {output_file}. Open it in a web browser to view.")

# Example usage
states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_STATES.geojson"
police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/INDIA/INDIA_POLICE_STATIONS.geojson"

create_hierarchical_map(states_geojson_path, police_stations_geojson_path)

