import folium
from folium import plugins
import json
import os
from pathlib import Path
import geopandas as gpd
import branca.colormap as cm

def load_geojson(file_path):
    """Load and validate GeoJSON file"""
    try:
        return gpd.read_file(file_path)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def create_base_map():
    """Create the base map centered on India"""
    return folium.Map(
        location=[20.5937, 78.9629],  # Center of India
        zoom_start=5,
        tiles='cartodbpositron',
        prefer_canvas=True
    )

def add_india_layers(map_obj, india_folder):
    """Add main India layers with zoom threshold"""
    # Create layer groups
    states = folium.FeatureGroup(name="States", show=True)
    districts = folium.FeatureGroup(name="Districts", show=False)
    police = folium.FeatureGroup(name="Police Stations", show=False)
    railways = folium.FeatureGroup(name="Railways", show=False)
    highways = folium.FeatureGroup(name="National Highways", show=False)
    energy = folium.FeatureGroup(name="Energy Plants", show=False)

    # Load and add states
    states_data = load_geojson(os.path.join(india_folder, 'INDIA_STATES.geojson'))
    if states_data is not None:
        folium.GeoJson(
            states_data,
            name='States',
            style_function=lambda x: {
                'fillColor': '#ffcccb',
                'color': 'black',
                'weight': 2,
                'fillOpacity': 0.2
            }
        ).add_to(states)

    # Load and add police stations with clustering
    police_data = load_geojson(os.path.join(india_folder, 'INDIA_POLICE_STATIONS.geojson'))
    if police_data is not None:
        marker_cluster = plugins.MarkerCluster(name="Police Stations")
        for idx, row in police_data.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=8,
                popup=f"Police Station: {row.get('name', 'N/A')}",
                color='red',
                fill=True
            ).add_to(marker_cluster)
        marker_cluster.add_to(police)

    # Add other infrastructure layers
    infrastructure_files = {
        'INDIAN_RAILWAYS.geojson': (railways, 'blue', 'Railway'),
        'INDIA_NATIONAL_HIGHWAY.geojson': (highways, 'orange', 'Highway'),
        'INDIA_ENERGY_PLANTS.geojson': (energy, 'purple', 'Energy Plant')
    }

    for filename, (feature_group, color, label) in infrastructure_files.items():
        data = load_geojson(os.path.join(india_folder, filename))
        if data is not None:
            folium.GeoJson(
                data,
                name=label,
                style_function=lambda x, color=color: {
                    'color': color,
                    'weight': 2
                }
            ).add_to(feature_group)

    # Add all feature groups to map
    for feature_group in [states, districts, police, railways, highways, energy]:
        feature_group.add_to(map_obj)

def add_metro_cities(map_obj, metro_folder):
    """Add metropolitan cities as a separate layer"""
    metro_group = folium.FeatureGroup(name="Metropolitan Cities", show=False)
    
    for city_file in os.listdir(metro_folder):
        if city_file.endswith('.geojson'):
            city_data = load_geojson(os.path.join(metro_folder, city_file))
            if city_data is not None:
                city_name = city_file.replace('.geojson', '')
                folium.GeoJson(
                    city_data,
                    name=city_name,
                    style_function=lambda x: {
                        'fillColor': '#ff7800',
                        'color': 'orange',
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    popup=folium.Popup(city_name, parse_html=True)
                ).add_to(metro_group)
    
    metro_group.add_to(map_obj)

def add_state_details(map_obj, states_folder):
    """Add detailed state information with zoom threshold"""
    for state_folder in os.listdir(states_folder):
        state_path = os.path.join(states_folder, state_folder)
        if os.path.isdir(state_path):
            state_group = folium.FeatureGroup(name=f"{state_folder} Details", show=False)
            
            for file in os.listdir(state_path):
                if file.endswith('.geojson'):
                    data = load_geojson(os.path.join(state_path, file))
                    if data is not None:
                        layer_name = file.replace('.geojson', '').replace(f"{state_folder}_", '')
                        folium.GeoJson(
                            data,
                            name=layer_name,
                            style_function=lambda x: {
                                'fillColor': '#3388ff',
                                'color': 'blue',
                                'weight': 1,
                                'fillOpacity': 0.2
                            },
                            popup=folium.Popup(layer_name, parse_html=True)
                        ).add_to(state_group)
            
            state_group.add_to(map_obj)

def create_interactive_map(india_folder, metro_folder, states_folder):
    """Create the main interactive map"""
    try:
        # Create base map
        m = create_base_map()
        
        # Add scale bar (this is built-in with Folium)
        folium.plugins.MiniMap().add_to(m)
        
        # Add fullscreen button
        folium.plugins.Fullscreen().add_to(m)
        
        # Add main India layers
        add_india_layers(m, india_folder)
        
        # Add metropolitan cities
        add_metro_cities(m, metro_folder)
        
        # Add state details
        add_state_details(m, states_folder)
        
        # Add layer control
        folium.LayerControl(collapsed=False).add_to(m)
        
        # Add search functionality
        plugins.Search(
            layer=folium.FeatureGroup(),
            geom_type='Point',
            placeholder='Search for a location',
            collapsed=False,
            search_label='name'
        ).add_to(m)
        
        # Add mini map
        plugins.MiniMap().add_to(m)
        
        # Save the map
        output_path = 'interactive_india_map.html'
        m.save(output_path)
        print(f"Map successfully created and saved as {output_path}")
        
    except Exception as e:
        print(f"Error creating map: {e}")


if __name__ == "__main__":
    # Define folder paths
    india_folder = "INDIA"
    metro_folder = "METROPOLITAN CITIES"
    states_folder = "STATES"
    
    # Create the interactive map
    create_interactive_map(india_folder, metro_folder, states_folder)
