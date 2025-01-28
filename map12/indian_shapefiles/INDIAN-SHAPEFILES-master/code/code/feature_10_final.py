import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any

@st.cache_data
def load_data(states_geojson_path: str, crime_data_csv_path: str, police_stations_geojson_path: str) -> Tuple[Dict, pd.DataFrame, Dict]:
    """
    Load and cache the required data files.
    """
    try:
        with open(states_geojson_path, 'r', encoding='utf-8') as f:
            states_geojson = json.load(f)

        # Load crime data and convert relevant columns to string and dates
        crime_data = pd.read_csv(crime_data_csv_path)
        crime_data['State/UT Name'] = crime_data['State/UT Name'].astype(str)
        crime_data['District'] = crime_data['District'].astype(str)
        crime_data['Police Station'] = crime_data['Police Station'].astype(str)
        crime_data['Category'] = crime_data['Category'].astype(str)
        crime_data['Sub Category'] = crime_data['Sub Category'].astype(str)
        
        # Convert date columns to datetime
        crime_data['Complaint Date'] = pd.to_datetime(crime_data['Complaint Date'], errors='coerce')
        crime_data['Incident Date'] = pd.to_datetime(crime_data['Incident Date'], errors='coerce')

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
    districts_geojson: Dict,
    crime_data: pd.DataFrame,
    selected_state: str,
    selected_district: str,
    selected_police_station: str,
    selected_category: str,
    selected_subcategory: str,
    start_date: pd.Timestamp,  # New parameter
    end_date: pd.Timestamp     # New parameter
) -> folium.Map:
    """
    Create an interactive crime rate map with filters and zooming.
    """
    # Initialize map centered on India
    india_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    # Filter data based on selections
    filtered_data = crime_data.copy()
    highlight_state = None
    highlight_district = None

    # Add date range filter
    filtered_data = filtered_data[
        (filtered_data['Complaint Date'].dt.date >= start_date.date()) &
        (filtered_data['Complaint Date'].dt.date <= end_date.date())
    ]

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

    if selected_police_station != "All Police Stations":
        filtered_data = filtered_data[filtered_data['Police Station'] == selected_police_station]

    if selected_category != "All Categories":
        filtered_data = filtered_data[filtered_data['Category'] == selected_category]

    if selected_subcategory != "All Sub Categories":
        filtered_data = filtered_data[filtered_data['Sub Category'] == selected_subcategory]

    # Function to get bounds from coordinates
    def get_bounds(data):
        if not data.empty and 'Latitude' in data.columns and 'Longitude' in data.columns:
            valid_coords = data[data['Latitude'].notna() & data['Longitude'].notna()]
            if not valid_coords.empty:
                min_lat = valid_coords['Latitude'].min()
                max_lat = valid_coords['Latitude'].max()
                min_lon = valid_coords['Longitude'].min()
                max_lon = valid_coords['Longitude'].max()
                return [[min_lat, min_lon], [max_lat, max_lon]]
        return None

    # Add appropriate boundaries with conditional styling
    def style_function(feature):
        default_style = {
            'fillColor': '#ffaf00',
            'color': 'white',
            'weight': 2,
            'fillOpacity': 0.3
        }

        if highlight_district:
            # If district is selected, only highlight the specific district
            if (feature.get('properties', {}).get('DISTRICT') == selected_district and
                feature.get('properties', {}).get('STATE') == selected_state):
                return {
                    'fillColor': '#ff6b6b',
                    'color': 'red',
                    'weight': 3,
                    'fillOpacity': 0.4
                }
            return {'fillOpacity': 0.1, 'weight': 1}
        elif highlight_state:
            # If only state is selected, highlight the entire state
            if feature.get('properties', {}).get('STNAME') == selected_state:
                return {
                    'fillColor': '#ff6b6b',
                    'color': 'red',
                    'weight': 3,
                    'fillOpacity': 0.4
                }
        return default_style

    # Add state boundaries
    folium.GeoJson(
        states_geojson,
        style_function=style_function,
        name="States"
    ).add_to(india_map)

    # Add district boundaries if available and state is selected
    if districts_geojson and selected_state != "All States":
        folium.GeoJson(
            districts_geojson,
            style_function=style_function,
            name="Districts"
        ).add_to(india_map)

    # Create marker cluster for better performance
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
                            <p><strong>Category:</strong> {row['Category']}</p>
                            <p><strong>Sub Category:</strong> {row['Sub Category']}</p>
                            <p><strong>Status:</strong> {row['Status']}</p>
                            <p><strong>Incident Date:</strong> {row['Incident Date']}</p>
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

    # Adjust map bounds based on filtered data
    bounds = get_bounds(filtered_data)
    if bounds:
        india_map.fit_bounds(bounds)
    elif highlight_district:
        # If no points but district selected, zoom to district bounds
        coordinates = highlight_district['geometry']['coordinates'][0][0]
        if coordinates:
            bounds = [
                [min(p[1] for p in coordinates), min(p[0] for p in coordinates)],
                [max(p[1] for p in coordinates), max(p[0] for p in coordinates)]
            ]
            india_map.fit_bounds(bounds)
    elif highlight_state:
        # If no points but state selected, zoom to state bounds
        coordinates = highlight_state['geometry']['coordinates'][0][0]
        if coordinates:
            bounds = [
                [min(p[1] for p in coordinates), min(p[0] for p in coordinates)],
                [max(p[1] for p in coordinates), max(p[0] for p in coordinates)]
            ]
            india_map.fit_bounds(bounds)

    # Adjust zoom level based on selection
    if selected_police_station != "All Police Stations":
        india_map.zoom_start = 15
    elif selected_district != "All Districts":
        india_map.zoom_start = 10
    elif selected_state != "All States":
        india_map.zoom_start = 7

    return india_map

def main():
    """Main application function."""
    st.set_page_config(
        page_title="Crime Map",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Add custom CSS to make the map full screen and remove padding
    st.markdown("""
        <style>
            .block-container {
                padding-top: 0;
                padding-bottom: 0;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            [data-testid="stSidebar"] {
                width: 300px !important;
            }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    try:
        # Load data paths
        states_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/code/code/data/INDIA_STATES.geojson"
        districts_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/code/code/data/INDIA_DISTRICTS.geojson"
        crime_data_csv_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/code/code/data/crime_data.csv"
        police_stations_geojson_path = "/home/i4c/Documents/map-this/map12/indian_shapefiles/INDIAN-SHAPEFILES-master/code/code/data/INDIA_POLICE_STATIONS.geojson"

        # Validate file existence
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

        # Load districts GeoJSON if available
        districts_geojson = None
        if os.path.exists(districts_geojson_path):
            with open(districts_geojson_path, 'r', encoding='utf-8') as f:
                districts_geojson = json.load(f)

        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

        # Sidebar filters
        with st.sidebar:
            st.header("Filter Options")

            with st.expander("Show/Hide Filters", expanded=True):
                # Date Range Filter
                st.subheader("Complaint Date Filter")
                
                # Get min and max dates from the data
                min_date = crime_data['Complaint Date'].min().date()
                max_date = crime_data['Complaint Date'].max().date()
                
                # Date range selector
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input(
                        "Start Date",
                        value=min_date,
                        min_value=min_date,
                        max_value=max_date
                    )
                with col2:
                    end_date = st.date_input(
                        "End Date",
                        value=max_date,
                        min_value=min_date,
                        max_value=max_date
                    )

                # Convert to pandas Timestamp for consistent datetime handling
                start_date = pd.Timestamp(start_date)
                end_date = pd.Timestamp(end_date)

                # Location Filters
                st.subheader("Location Filters")
                
                # State filter
                state_options = ["All States"] + sorted(crime_data['State/UT Name'].unique().tolist())
                selected_state = st.selectbox(
                    "Select State",
                    state_options,
                    help="Filter crime data by state"
                )

                # District filter
                district_data = crime_data[crime_data['State/UT Name'] == selected_state] if selected_state != "All States" else crime_data
                district_options = ["All Districts"] + sorted(district_data['District'].unique().tolist())
                selected_district = st.selectbox(
                    "Select District",
                    district_options,
                    help="Filter crime data by district"
                )

                # Police Station filter
                station_data = district_data[district_data['District'] == selected_district] if selected_district != "All Districts" else district_data
                station_options = ["All Police Stations"] + sorted(station_data['Police Station'].unique().tolist())
                selected_police_station = st.selectbox(
                    "Select Police Station",
                    station_options,
                    help="Filter crime data by police station"
                )

                # Crime Category Filters
                st.subheader("Crime Filters")

                # Category filter
                category_options = ["All Categories"] + sorted(crime_data['Category'].unique().tolist())
                selected_category = st.selectbox(
                    "Select Crime Category",
                    category_options,
                    help="Filter by type of crime"
                )

                # Sub Category filter - dependent on Category selection
                subcategory_data = crime_data[crime_data['Category'] == selected_category] if selected_category != "All Categories" else crime_data
                subcategory_options = ["All Sub Categories"] + sorted(subcategory_data['Sub Category'].unique().tolist())
                selected_subcategory = st.selectbox(
                    "Select Crime Sub Category",
                    subcategory_options,
                    help="Filter by specific type of crime"
                )

                if st.button("Reset Filters", type="primary"):
                    st.experimental_rerun()

        # Create and display map with date range parameters
        crime_map = create_crime_rate_map(
            states_geojson,
            districts_geojson,
            crime_data,
            selected_state,
            selected_district,
            selected_police_station,
            selected_category,
            selected_subcategory,
            start_date,
            end_date
        )

        # Display map with full height
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



