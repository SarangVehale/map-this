import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from datetime import datetime
import numpy as np

def clean_amount(amount):
    """Clean and convert amount strings to float."""
    if pd.isna(amount):
        return 0.0
    try:
        return float(''.join(filter(lambda x: x.isdigit() or x == '.', str(amount))))
    except ValueError:
        return 0.0

def get_coordinates(district, state, police_station):
    """Get coordinates with hierarchical fallback."""
    geolocator = Nominatim(user_agent="crime_map")
    locations_to_try = [
        f"{police_station}, {district}, {state}, India",
        f"{district}, {state}, India",
        f"{state}, India"
    ]
    
    for location_str in locations_to_try:
        try:
            location_data = geolocator.geocode(location_str)
            if location_data:
                return (location_data.latitude, location_data.longitude)
        except (GeocoderTimedOut, GeocoderUnavailable):
            continue
    return None

def create_crime_map(csv_file):
    # Read CSV file with the exact column names
    try:
        df = pd.read_csv(csv_file)
        print("Columns in the DataFrame:", df.columns.tolist())  # Debug print
    except FileNotFoundError:
        print(f"Error: File {csv_file} not found")
        return
    except pd.errors.EmptyDataError:
        print("Error: The CSV file is empty")
        return

    # Convert amount columns to numeric
    df['Fraudulent Amount'] = df['Fraudulent Amount'].apply(clean_amount)
    df['Lien Amount'] = df['Lien Amount'].apply(clean_amount)

    # Convert dates to datetime
    date_columns = ['Incident Date', 'Complaint Date']
    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Create base map centered on India
    india_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

    # Create different marker clusters for different zoom levels
    state_cluster = MarkerCluster(name='States View')
    district_cluster = MarkerCluster(name='Districts View')
    station_cluster = MarkerCluster(name='Police Stations View')

    # Create summary statistics using exact column names
    state_stats = df.groupby('State/UT Name').agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum'
    }).reset_index()

    district_stats = df.groupby(['State/UT Name', 'District']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum'
    }).reset_index()

    station_stats = df.groupby(['State/UT Name', 'District', 'Police Station']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum',
        'Category': lambda x: ', '.join(set(x))
    }).reset_index()

    # Create color scale for amount visualization
    def get_color(amount):
        if amount == 0:
            return 'gray'
        elif amount < 10000:
            return 'green'
        elif amount < 100000:
            return 'yellow'
        elif amount < 1000000:
            return 'orange'
        else:
            return 'red'

    # Add state-level markers
    for _, row in state_stats.iterrows():
        coords = get_coordinates(None, row['State/UT Name'], None)
        if coords:
            popup_content = f"""
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}
            """
            folium.CircleMarker(
                location=coords,
                radius=20,
                popup=folium.Popup(popup_content, max_width=300),
                color=get_color(row['Fraudulent Amount']),
                fill=True,
                fill_opacity=0.7
            ).add_to(state_cluster)

    # Add district-level markers
    for _, row in district_stats.iterrows():
        coords = get_coordinates(row['District'], row['State/UT Name'], None)
        if coords:
            popup_content = f"""
                <b>District:</b> {row['District']}<br>
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}
            """
            folium.CircleMarker(
                location=coords,
                radius=15,
                popup=folium.Popup(popup_content, max_width=300),
                color=get_color(row['Fraudulent Amount']),
                fill=True,
                fill_opacity=0.7
            ).add_to(district_cluster)

    # Add police station-level markers
    for _, row in station_stats.iterrows():
        coords = get_coordinates(row['District'], row['State/UT Name'], row['Police Station'])
        if coords:
            popup_content = f"""
                <b>Police Station:</b> {row['Police Station']}<br>
                <b>District:</b> {row['District']}<br>
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}<br>
                <b>Categories:</b> {row['Category']}
            """
            folium.Marker(
                location=coords,
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color=get_color(row['Fraudulent Amount']))
            ).add_to(station_cluster)

    # Add heatmap layer
    heat_data = []
    for _, row in station_stats.iterrows():
        coords = get_coordinates(row['District'], row['State/UT Name'], row['Police Station'])
        if coords:
            heat_data.append([coords[0], coords[1], row['S No.']])
    
    HeatMap(heat_data).add_to(folium.FeatureGroup(name='Heat Map').add_to(india_map))

    # Add all layers to map
    state_cluster.add_to(india_map)
    district_cluster.add_to(india_map)
    station_cluster.add_to(india_map)

    # Add layer control
    folium.LayerControl().add_to(india_map)

    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px">
    <p><strong>Amount Range</strong></p>
    <p><i class="fa fa-circle" style="color:red"></i> > ₹10,00,000</p>
    <p><i class="fa fa-circle" style="color:orange"></i> ₹1,00,000 - ₹10,00,000</p>
    <p><i class="fa fa-circle" style="color:yellow"></i> ₹10,000 - ₹1,00,000</p>
    <p><i class="fa fa-circle" style="color:green"></i> < ₹10,000</p>
    <p><i class="fa fa-circle" style="color:gray"></i> No Amount</p>
    </div>
    """
    india_map.get_root().html.add_child(folium.Element(legend_html))

    # Save map
    india_map.save('crime_map.html')
    print("Map has been created as 'crime_map.html'")

    # Print summary statistics
    print("\nSummary Statistics:")
    print(f"Total number of cases: {len(df)}")
    print(f"Total fraudulent amount: ₹{df['Fraudulent Amount'].sum():,.2f}")
    print(f"Number of states affected: {len(state_stats)}")
    print(f"Number of districts affected: {len(district_stats)}")
    print(f"Number of police stations affected: {len(station_stats)}")

if __name__ == "__main__":
    create_crime_map('crime_data.csv')
