import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import os
from typing import Tuple, List, Dict, Any

# Configure the page (must be the first Streamlit command)
st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
    page_title="Crime Rate Map",
    page_icon="🗺️"
)







def main():
    """Main application function."""
    st.title("Interactive Crime Rate Map")
    st.markdown("---")

    try:
        # File paths
        states_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_STATES.geojson"
        districts_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_DISTRICTS.geojson"
        crime_data_csv_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/crime_data.csv"
        police_stations_geojson_path = "/mnt/c/Users/Sarang/Downloads/crimeRateMapping/transfer/INDIA_POLICE_STATIONS.geojson"

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

        districts_geojson = None
        if os.path.exists(districts_geojson_path):
            with open(districts_geojson_path, 'r', encoding='utf-8') as f:
                districts_geojson = json.load(f)

        crime_data, unmatched_entries = match_coordinates(crime_data, police_stations_data)
        crime_data = approximate_missing_locations(crime_data)

        # Sidebar filters
        with st.sidebar:
            st.header("Filter Options")
            state_options = ["All States"] + sorted(crime_data['State/UT Name'].unique().tolist())
            selected_state = st.selectbox("Select State", state_options)
            district_data = crime_data[crime_data['State/UT Name'] == selected_state] if selected_state != "All States" else crime_data
            district_options = ["All Districts"] + sorted(district_data['District'].unique().tolist())
            selected_district = st.selectbox("Select District", district_options)

            if st.button("Reset Filters"):
                st.experimental_rerun()

        # Create and display map
        crime_map = create_crime_rate_map(
            states_geojson, districts_geojson, crime_data, selected_state, selected_district, "All Police Stations"
        )
        st_folium(crime_map, width="100%", height=800)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        if st.checkbox("Show error details"):
            st.exception(e)

if __name__ == "__main__":
    main()
