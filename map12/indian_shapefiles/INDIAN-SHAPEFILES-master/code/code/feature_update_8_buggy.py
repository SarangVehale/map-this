import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any


class StyleFunction:
    """
    Class to create a callable style function that can be pickled.
    """
    def __init__(self, highlight_state, highlight_district, selected_state, selected_district):
        self.highlight_state = highlight_state
        self.highlight_district = highlight_district
        self.selected_state = selected_state
        self.selected_district = selected_district

    def __call__(self, feature):
        return get_style_dict(
            feature,
            self.highlight_state,
            self.highlight_district,
            self.selected_state,
            self.selected_district
        )
    

# Configure the page to use full screen width and remove padding
st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
    page_title="Crime Rate Map",
    page_icon="🗺️"
)

# Custom CSS to remove padding and make the map full screen
st.markdown("""
    <style>
        .main > div {
            padding-top: 0rem;
            padding-left: 0rem;
            padding-right: 0rem;
            padding-bottom: 0rem;
        }
        .stApp {
            margin: 0 auto;
        }
        .css-1d391kg {
            padding-top: 0rem;
        }
        .css-18e3th9 {
            padding-top: 0rem;
            padding-bottom: 0rem;
            padding-left: 0rem;
            padding-right: 0rem;
        }
        .css-1a1fmpi {
            padding-top: 0rem;
            padding-bottom: 0rem;
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
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .streamlit-expanderHeader {
            background-color: #f3f4f6;
            border-radius: 0.375rem;
            padding: 0.5rem 1rem;
        }
        .streamlit-expanderContent {
            background-color: white;
            border-radius: 0.375rem;
            padding: 1rem;
            margin-top: 0.5rem;
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
        .stSelectbox > div > div:hover {
            border-color: #4f46e5;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_style_dict(
    feature: Dict,
    highlight_state: str = None,
    highlight_district: str = None,
    selected_state: str = None,
    selected_district: str = None
) -> Dict[str, Any]:
    """
    Get the style dictionary for a GeoJSON feature.
    """
    default_style = {
        'fillColor': '#6366f1',
        'color': '#4f46e5',
        'weight': 1.5,
        'fillOpacity': 0.2
    }
    
    if highlight_district and selected_district and selected_state:
        if (feature.get('properties', {}).get('DISTRICT') == selected_district and 
            feature.get('properties', {}).get('STATE') == selected_state):
            return {
                'fillColor': '#ef4444',
                'color': '#dc2626',
                'weight': 2,
                'fillOpacity': 0.3
            }
        return {'fillOpacity': 0.1, 'weight': 1}
    elif highlight_state and selected_state:
        if feature.get('properties', {}).get('STNAME') == selected_state:
            return {
                'fillColor': '#ef4444',
                'color': '#dc2626',
                'weight': 2,
                'fillOpacity': 0.3
            }
    return default_style

@st.cache_data(ttl=300)
def get_bounds(data: pd.DataFrame) -> List[List[float]]:
    """
    Calculate bounds for the map based on data coordinates.
    """
    if not data.empty and 'Latitude' in data.columns and 'Longitude' in data.columns:
        valid_coords = data[data['Latitude'].notna() & data['Longitude'].notna()]
        if not valid_coords.empty:
            min_lat = valid_coords['Latitude'].min()
            max_lat = valid_coords['Latitude'].max()
            min_lon = valid_coords['Longitude'].min()
            max_lon = valid_coords['Longitude'].max()
            return [[min_lat, min_lon], [max_lat, max_lon]]
    return None

@st.cache_data(ttl=300)
def create_popup_html(row: pd.Series) -> str:
    """
    Create HTML content for map markers.
    """
    return f"""
        <div style='font-family: Inter, system-ui, sans-serif; padding: 1rem; min-width: 200px;'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 1.125rem;'>Location Details</h4>
            <div style='border-top: 1px solid #e5e7eb; padding-top: 0.75rem;'>
                <p style='margin: 0 0 0.5rem 0;'><strong style='color: #4b5563;'>State:</strong> {row['State/UT Name']}</p>
                <p style='margin: 0 0 0.5rem 0;'><strong style='color: #4b5563;'>District:</strong> {row['District']}</p>
                <p style='margin: 0;'><strong style='color: #4b5563;'>Police Station:</strong> {row['Police Station']}</p>
            </div>
        </div>
    """


@st.cache_data(ttl=300)
def create_crime_rate_map(
    states_geojson: Dict,
    districts_geojson: Dict,
    crime_data: pd.DataFrame,
    selected_state: str,
    selected_district: str,
    selected_police_station: str
) -> folium.Map:
    """
    Create an interactive crime rate map with filters and zooming.
    """
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
                if (feature['properties'].get('DISTRICT') == selected_district and 
                    feature['properties'].get('STATE') == selected_state):
                    highlight_district = feature
                    break

    # Create style function instances
    states_style = StyleFunction(highlight_state, highlight_district, selected_state, selected_district)
    districts_style = StyleFunction(highlight_state, highlight_district, selected_state, selected_district)

    # Add GeoJSON layers with pickable style functions
    folium.GeoJson(
        states_geojson,
        style_function=states_style,
        name="States"
    ).add_to(india_map)

    if districts_geojson and selected_state != "All States":
        folium.GeoJson(
            districts_geojson,
            style_function=districts_style,
            name="Districts"
        ).add_to(india_map)
        
    if districts_geojson and selected_state != "All States":
        folium.GeoJson(
            districts_geojson,
            style_function=lambda x: get_style_dict(
                x,
                highlight_state=highlight_state,
                highlight_district=highlight_district,
                selected_state=selected_state,
                selected_district=selected_district
            ),
            name="Districts"
        ).add_to(india_map)

    # Add markers
    marker_cluster = MarkerCluster(
        options={
            'maxClusterRadius': 30,
            'spiderfyOnMaxZoom': True,
            'disableClusteringAtZoom': 15
        }
    ).add_to(india_map)

    for _, row in filtered_data.iterrows():
        try:
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                lat, lon = float(row['Latitude']), float(row['Longitude'])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    popup_html = create_popup_html(row)
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=6,
                        color='#ef4444',
                        fill=True,
                        fillColor='#ef4444',
                        fillOpacity=0.7,
                        weight=2,
                        popup=folium.Popup(popup_html, max_width=300)
                    ).add_to(marker_cluster)
        except Exception:
            continue

    # Set map bounds
    bounds = get_bounds(filtered_data)
    if bounds:
        india_map.fit_bounds(bounds)
    elif highlight_district:
        coordinates = highlight_district['geometry']['coordinates'][0][0]
        if coordinates:
            bounds = [
                [min(p[1] for p in coordinates), min(p[0] for p in coordinates)],
                [max(p[1] for p in coordinates), max(p[0] for p in coordinates)]
            ]
            india_map.fit_bounds(bounds)
    elif highlight_state:
        coordinates = highlight_state['geometry']['coordinates'][0][0]
        if coordinates:
            bounds = [
                [min(p[1] for p in coordinates), min(p[0] for p in coordinates)],
                [max(p[1] for p in coordinates), max(p[0] for p in coordinates)]
            ]
            india_map.fit_bounds(bounds)

    # Set zoom level based on selection
    if selected_police_station != "All Police Stations":
        india_map.zoom_start = 15
    elif selected_district != "All Districts":
        india_map.zoom_start = 10
    elif selected_state != "All States":
        india_map.zoom_start = 7

    return india_map

@st.cache_data(ttl=3600)
def match_coordinates(crime_data: pd.DataFrame, police_stations_data: Dict) -> Tuple[pd.DataFrame, List[str]]:
    """
    Match crime data with police station coordinates.
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

@st.cache_data(ttl=3600)
def approximate_missing_locations(crime_data: pd.DataFrame) -> pd.DataFrame:
    """
    Approximate missing location data using district or state centroids.
    """
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

@st.cache_data(ttl=3600)
def load_data(states_geojson_path: str, crime_data_csv_path: str, police_stations_geojson_path: str) -> Tuple[Dict, pd.DataFrame, Dict]:
    """
    Load and prepare data from files.
    """
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
        st.error(f"Error loading data: {e}")
        raise

def main():
    """Main application function."""
    try:
        # Load data
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_STATES.geojson"
        districts_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_DISTRICTS.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_POLICE_STATIONS.geojson"
        
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

        # Ensure data types
        crime_data['State/UT Name'] = crime_data['State/UT Name'].astype(str)
        crime_data['District'] = crime_data['District'].astype(str)
        crime_data['Police Station'] = crime_data['Police Station'].astype(str)

        # Sidebar filters
        with st.sidebar:
            st.markdown("""
                <div style='padding: 1rem 0;'>
                    <h2 style='font-size: 1.25rem; font-weight: 600; color: #1f2937; margin-bottom: 1rem;'>
                        Filter Options
                    </h2>
                </div>
            """, unsafe_allow_html=True)
            
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

                st.button("Reset Filters", type="primary", key="reset_filters")

        # Create and display map
        crime_map = create_crime_rate_map(
            states_geojson,
            districts_geojson,
            crime_data,
            selected_state,
            selected_district,
            selected_police_station
        )

        st_folium(
            crime_map,
            width="100%",
            height=1000,
            returned_objects=["last_active_drawing"]
        )

    except Exception as e:
        st.error("An error occurred while loading the application.")
        st.error(f"Error details: {str(e)}")
        if st.checkbox("Show detailed error"):
            st.exception(e)

if __name__ == "__main__":
    main()


