import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any

# Configure the page
st.set_page_config(
    page_title="Interactive Crime Rate Map",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
        .main > div {
            padding: 2rem;
        }
        .stApp {
            margin: 0 auto;
        }
        .css-1d391kg {
            padding-top: 1rem;
        }
        .stButton>button {
            width: 100%;
            border-radius: 0.375rem;
            background-color: #4f46e5;
            color: white;
            font-weight: 500;
            padding: 0.625rem 1.25rem;
            transition: all 0.2s;
        }
        .stButton>button:hover {
            background-color: #4338ca;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .streamlit-expanderHeader {
            background-color: #f3f4f6;
            border-radius: 0.375rem;
            padding: 0.5rem 1rem;
        }
        [data-testid="stSidebar"] {
            background-color: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }
        .stSelectbox > div > div {
            background-color: white;
            border-radius: 0.375rem;
            border: 1px solid #e2e8f0;
        }
    </style>
""", unsafe_allow_html=True)

def style_function(feature, highlight_state, highlight_district, selected_state, selected_district):
    """Style function for GeoJSON layers."""
    default_style = {
        'fillColor': '#ffaf00',
        'color': 'black',
        'weight': 2,
        'fillOpacity': 0.3
    }
    
    if highlight_district and selected_district and selected_state:
        if (feature.get('properties', {}).get('dtname') == selected_district and 
            feature.get('properties', {}).get('stname') == selected_state):
            return {
                'fillColor': '#ff6b6b',
                'color': 'red',
                'weight': 3,
                'fillOpacity': 0.4
            }
        return {'fillOpacity': 0.1, 'weight': 1}
    elif highlight_state and selected_state:
        if feature.get('properties', {}).get('stname') == selected_state:
            return {
                'fillColor': '#ff6b6b',
                'color': 'red',
                'weight': 3,
                'fillOpacity': 0.4
            }
    return default_style

def highlight_function(feature):
    """Highlight function for GeoJSON layers."""
    return {
        'fillColor': '#ffd700',
        'color': '#000000',
        'weight': 3,
        'fillOpacity': 0.7
    }

@st.cache_data
def load_data(states_geojson_path: str, crime_data_csv_path: str, police_stations_geojson_path: str) -> Tuple[Dict, pd.DataFrame, Dict]:
    """Load and cache the required data files."""
    try:
        with open(states_geojson_path, 'r', encoding='utf-8') as f:
            states_geojson = json.load(f)

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

                district_data = crime_data[
                    (crime_data['State/UT Name'] == state) &
                    (crime_data['District'] == district)
                ]
                district_coords = district_data[['Latitude', 'Longitude']].dropna()

                if not district_coords.empty:
                    crime_data.at[index, 'Latitude'] = float(district_coords['Latitude'].mean())
                    crime_data.at[index, 'Longitude'] = float(district_coords['Longitude'].mean())
                else:
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
    """Create an interactive crime rate map with enhanced interactivity."""
    india_map = folium.Map(
        location=[20.5937, 78.9629],
        zoom_start=5,
        tiles='CartoDB positron',
        control_scale=True
    )

    filtered_data = crime_data.copy()
    highlight_state = None
    highlight_district = None

    if selected_state != "All States":
        filtered_data = filtered_data[filtered_data['State/UT Name'] == selected_state]
        for feature in states_geojson['features']:
            if feature['properties'].get('STNAME') == selected_state:
                highlight_state = feature
                break

    if selected_district != "All Districts":
        filtered_data = filtered_data[filtered_data['District'] == selected_district]
        if districts_geojson:
            for feature in districts_geojson['features']:
                if (feature['properties'].get('dtname') == selected_district and 
                    feature['properties'].get('stname') == selected_state):
                    highlight_district = feature
                    break

    # Add GeoJSON layers with hover effects
    folium.GeoJson(
        states_geojson,
        style_function=lambda x: style_function(x, highlight_state, highlight_district, selected_state, selected_district),
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['STNAME'],
            aliases=['State:'],
            style=('background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;')
        ),
        name="States"
    ).add_to(india_map)

    if districts_geojson and selected_state != "All States":
        folium.GeoJson(
            districts_geojson,
            style_function=lambda x: style_function(x, highlight_state, highlight_district, selected_state, selected_district),
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['dtname'],
                aliases=['District:'],
                style=('background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;')
            ),
            name="Districts"
        ).add_to(india_map)

    # Add markers with clustering
    marker_cluster = MarkerCluster(
        options={
            'maxClusterRadius': 30,
            'spiderfyOnMaxZoom': True,
            'disableClusteringAtZoom': 15
        }
    ).add_to(india_map)

    # Add markers for crime locations with enhanced popups
    for _, row in filtered_data.iterrows():
        try:
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                lat, lon = float(row['Latitude']), float(row['Longitude'])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    popup_html = f"""
                        <div style='font-family: Arial, sans-serif; padding: 15px; min-width: 200px;'>
                            <h4 style='margin: 0 0 10px 0; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;'>
                                Location Details
                            </h4>
                            <div style='line-height: 1.6;'>
                                <p style='margin: 5px 0;'><strong style='color: #4b5563;'>State:</strong> {row['State/UT Name']}</p>
                                <p style='margin: 5px 0;'><strong style='color: #4b5563;'>District:</strong> {row['District']}</p>
                                <p style='margin: 5px 0;'><strong style='color: #4b5563;'>Police Station:</strong> {row['Police Station']}</p>
                            </div>
                        </div>
                    """
                    
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=8,
                        color='#ef4444',
                        fill=True,
                        fillColor='#ef4444',
                        fillOpacity=0.7,
                        weight=2,
                        popup=folium.Popup(popup_html, max_width=300)
                    ).add_to(marker_cluster)
        except Exception:
            continue

    # Add layer control
    folium.LayerControl().add_to(india_map)

    # Set appropriate zoom level
    if selected_police_station != "All Police Stations":
        station_data = filtered_data[filtered_data['Police Station'] == selected_police_station]
        if not station_data.empty:
            lat = station_data.iloc[0]['Latitude']
            lon = station_data.iloc[0]['Longitude']
            india_map.location = [lat, lon]
            india_map.zoom_start = 15
    elif selected_district != "All Districts" and highlight_district:
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
            india_map.zoom_start = 10
    elif selected_state != "All States" and highlight_state:
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
            india_map.zoom_start = 7

    return india_map

def main():
    """Main application function."""
    st.title("Interactive Crime Rate Map")
    st.markdown("---")

    try:
        # Load data
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_STATES.geojson"
        districts_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_DISTRICTS.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/data/INDIA_POLICE_STATIONS.geojson"
        
        # Check if required files exist
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

        districts_geojson = None
        if os.path.exists(districts_geojson_path):
            with open(districts_geojson_path, 'r', encoding='utf-8') as f:
                districts_geojson = json.load(f)

        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

        # Sidebar filters
        with st.sidebar:
            st.header("Filter Options")
            
            with st.expander("Location Filters", expanded=True):
                state_options = ["All States"] + sorted(crime_data['State/UT Name'].unique().tolist())
                selected_state = st.selectbox(
                    "Select State",
                    state_options,
                    help="Filter crime data by state"
                )

                district_data = crime_data[crime_data['State/UT Name'] == selected_state] if selected_state != "All States" else crime_data
                district_options = ["All Districts"] + sorted(district_data['District'].unique().tolist())
                selected_district = st.selectbox(
                    "Select District",
                    district_options,
                    help="Filter crime data by district"
                )

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