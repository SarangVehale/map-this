import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json 
import os
from folium.plugins import MarkerCluster
from folium.features import GeoJson

def load_data(states_geojson_path, crime_data_csv_path, police_stations_geojson_path):
    # Load GeoJSON data for states
    with open(states_geojson_path, 'r') as f:
        states_geojson = json.load(f)

    # Load crime data from CSV
    crime_data = pd.read_csv(crime_data_csv_path)

    # Load GeoJSON data for police stations
    with open(police_stations_geojson_path, 'r') as f:
        police_stations_data = json.load(f)

    return states_geojson, crime_data, police_stations_data


@st.cache_data
def match_coordinates(crime_data, police_stations_data):
    police_station_coords = {}
    for feature in police_stations_data['features']:
        try:
            properties = feature['properties']
            coordinates = feature['geometry']['coordinates']
            # Ensure coordinates are valid numbers
            if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
                lat = float(coordinates[1])
                lon = float(coordinates[0])
                if -90 <= lat <= 90 and -180 <= lon <= 180:  # Valid coordinate range
                    key = (str(properties['state']), str(properties['district']), str(properties['ps']))
                    police_station_coords[key] = (lat, lon)
        except (KeyError, ValueError, TypeError) as e:
            continue  # Skip invalid entries

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
def approximate_missing_locations(crime_data):
    for index, row in crime_data.iterrows():
        try:
            if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
                state = str(row['State/UT Name'])
                district = str(row['District'])

                # Calculate the district centroid if available
                district_data = crime_data[(crime_data['State/UT Name'] == state) & 
                                        (crime_data['District'] == district)]
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
        except Exception as e:
            continue  # Skip problematic entries

    return crime_data

def create_crime_rate_map(states_geojson, crime_data, police_stations_data, selected_state, selected_district, selected_police_station):
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

    try:
        # Initialize map view based on selection
        if selected_state != "All States":
            state_data = states_geojson['features']
            state_feature = next((feature for feature in state_data 
                                if feature['properties']['STNAME'] == selected_state), None)
            if state_feature:
                centroid = state_feature['geometry']['coordinates'][0][0]
                centroid_lat = sum([point[1] for point in centroid]) / len(centroid)
                centroid_lon = sum([point[0] for point in centroid]) / len(centroid)
                india_map.location = [centroid_lat, centroid_lon]
                india_map.zoom_start = 6

                # Highlight state boundaries
                GeoJson(
                    state_feature,
                    name="State Boundary",
                    style_function=lambda x: {
                        'fillColor': '#ffaf00',
                        'color': 'black',
                        'weight': 2,
                        'fillOpacity': 0.3
                    }
                ).add_to(india_map)

        if selected_district != "All Districts":
            district_data = filtered_data[filtered_data['District'] == selected_district]
            if not district_data.empty:
                centroid_lat = district_data['Latitude'].mean()
                centroid_lon = district_data['Longitude'].mean()
                if not pd.isna(centroid_lat) and not pd.isna(centroid_lon):
                    india_map.location = [centroid_lat, centroid_lon]
                    india_map.zoom_start = 7

                    # Highlight district boundaries
                    folium.CircleMarker(
                        [centroid_lat, centroid_lon],
                        radius=10,
                        color="red",
                        fill=True,
                        fill_color="red"
                    ).add_to(india_map)

        if selected_police_station != "All Police Stations":
            station_data = filtered_data[filtered_data['Police Station'] == selected_police_station]
            if not station_data.empty:
                station_lat = station_data['Latitude'].mean()
                station_lon = station_data['Longitude'].mean()
                if not pd.isna(station_lat) and not pd.isna(station_lon):
                    india_map.location = [station_lat, station_lon]
                    india_map.zoom_start = 8

                    # Highlight police station
                    folium.Marker(
                        [station_lat, station_lon],
                        popup=f"Police Station: {selected_police_station}"
                    ).add_to(india_map)

        # Function to safely add markers or circles
        def add_marker_or_circle(location, popup, radius=0, color="blue", 
                               fill=True, fill_color="blue", fill_opacity=0.6):
            try:
                if (location and 
                    isinstance(location, (list, tuple)) and 
                    len(location) >= 2 and 
                    not pd.isna(location[0]) and 
                    not pd.isna(location[1])):
                    
                    lat, lon = float(location[0]), float(location[1])
                    if -90 <= lat <= 90 and -180 <= lon <= 180:  # Valid coordinate range
                        if radius > 0:
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=radius,
                                color=color,
                                fill=fill,
                                fill_color=fill_color,
                                fill_opacity=fill_opacity,
                                popup=popup,
                            ).add_to(india_map)
                        else:
                            folium.Marker(
                                location=[lat, lon],
                                popup=popup,
                                icon=folium.Icon(color="blue", icon="info-sign"),
                            ).add_to(india_map)
            except Exception as e:
                pass  # Skip invalid markers

        # Add state-level markers
        state_counts = filtered_data.groupby('State/UT Name').size().reset_index(name='Crime Count')
        for _, row in state_counts.iterrows():
            state_name = row['State/UT Name']
            crime_count = row['Crime Count']
            state_data = filtered_data[filtered_data['State/UT Name'] == state_name]
            centroid_lat = state_data['Latitude'].mean()
            centroid_lon = state_data['Longitude'].mean()

            add_marker_or_circle(
                [centroid_lat, centroid_lon],
                f"<b>{state_name}</b><br>Total Crimes: {crime_count}",
                radius=min(20, crime_count / 10),
                color="red",
                fill_color="red"
            )

        # Add district-level circle markers
        district_counts = filtered_data.groupby(['State/UT Name', 'District']).size().reset_index(name='Crime Count')
        for _, row in district_counts.iterrows():
            district_name = row['District']
            crime_count = row['Crime Count']
            district_data = filtered_data[filtered_data['District'] == district_name]
            centroid_lat = district_data['Latitude'].mean()
            centroid_lon = district_data['Longitude'].mean()

            add_marker_or_circle(
                [centroid_lat, centroid_lon],
                f"<b>{district_name}</b><br>Total Crimes: {crime_count}",
                radius=min(15, crime_count / 5),
                color="orange",
                fill_color="orange"
            )

        # Add police station-level markers using MarkerCluster
        police_station_counts = filtered_data.groupby(
            ['State/UT Name', 'District', 'Police Station']
        ).size().reset_index(name='Crime Count')
        
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
                    popup=folium.Popup(
                        f"<b>Police Station: {police_station_name}</b><br>Total Crimes: {crime_count}"
                    ),
                    icon=folium.Icon(color="blue", icon="info-sign"),
                ).add_to(marker_cluster)

        # Add layer control for interactivity
        folium.LayerControl().add_to(india_map)

    except Exception as e:
        st.error(f"Error creating map visualization: {str(e)}")

    return india_map

def main():
    st.set_page_config(
        page_title="Interactive Crime Rate Map",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    with st.container():
        st.title("Interactive Crime Rate Map")
        st.markdown("---")

    try:
        # Load data
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_STATES.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_POLICE_STATIONS.geojson"
        
        # Validate file existence
        for file_path in [states_geojson_path, crime_data_csv_path, police_stations_geojson_path]:
            if not os.path.exists(file_path):
                st.error(f"File not found: {file_path}")
                return

        states_geojson, crime_data, police_stations_data = load_data(
            states_geojson_path,
            crime_data_csv_path,
            police_stations_geojson_path
        )

        # Validate required columns
        required_columns = ['State/UT Name', 'District', 'Police Station']
        missing_columns = [col for col in required_columns if col not in crime_data.columns]
        if missing_columns:
            st.error(f"Missing required columns in crime data: {', '.join(missing_columns)}")
            return

        # Match coordinates and approximate missing data
        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

        # Sidebar with collapsible filters
        with st.sidebar:
            st.header("Filter Options")
            
            # Add an expander for collapsible filters
            with st.expander("Show/Hide Filters", expanded=True):
                # State filter
                state_options = ["All States"] + sorted(list(crime_data['State/UT Name'].unique()))
                selected_state = st.selectbox(
                    "Select State",
                    state_options,
                    help="Filter crime data by state"
                )

                # District filter
                if selected_state != "All States":
                    district_options = ["All Districts"] + sorted(list(
                        crime_data[crime_data['State/UT Name'] == selected_state]['District'].unique()
                    ))
                else:
                    district_options = ["All Districts"]
                
                selected_district = st.selectbox(
                    "Select District",
                    district_options,
                    help="Filter crime data by district"
                )

                # Police Station filter
                if selected_state != "All States" and selected_district != "All Districts":
                    police_station_options = ["All Police Stations"] + sorted(list(
                        crime_data[
                            (crime_data['State/UT Name'] == selected_state) & 
                            (crime_data['District'] == selected_district)
                        ]['Police Station'].unique()
                    ))
                else:
                    police_station_options = ["All Police Stations"]
                
                selected_police_station = st.selectbox(
                    "Select Police Station",
                    police_station_options,
                    help="Filter crime data by police station"
                )

                # Add a reset filters button
                if st.button("Reset Filters"):
                    selected_state = "All States"
                    selected_district = "All Districts"
                    selected_police_station = "All Police Stations"
                    st.experimental_rerun()

        # Create the map with selected filters in the main content area
        crime_map = create_crime_rate_map(
            states_geojson,
            crime_data,
            police_stations_data,
            selected_state,
            selected_district,
            selected_police_station
        )

        # Display the map in the main area with full width
        st_folium(
            crime_map,
            width="100%",
            height=800,
            returned_objects=["last_active_drawing"]
        )

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.error("Please check if all required files are available and properly formatted.")
        st.exception(e)  # This will show the full error traceback in development

if __name__ == "__main__":
    main()
