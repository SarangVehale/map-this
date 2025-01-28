import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap
import sqlite3
import hashlib

def get_cached_coordinates(location_string, conn):
    """Get coordinates from the cache database"""
    location_hash = hashlib.md5(location_string.encode()).hexdigest()
    c = conn.cursor()
    c.execute("SELECT latitude, longitude FROM locations WHERE location_hash = ?", (location_hash,))
    result = c.fetchone()
    return result if result else (None, None)

def create_crime_map(csv_file):
    # Connect to the cache database
    try:
        conn = sqlite3.connect('locations.db')
    except sqlite3.Error as e:
        print("Error connecting to cache database. Please run preprocess_locations.py first.")
        return
    
    # Read CSV file
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: File {csv_file} not found")
        return
    
    # Convert amount columns to numeric
    df['Fraudulent Amount'] = pd.to_numeric(df['Fraudulent Amount'], errors='coerce').fillna(0)
    df['Lien Amount'] = pd.to_numeric(df['Lien Amount'], errors='coerce').fillna(0)

    # Create base map
    india_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
    
    # Create marker clusters
    state_cluster = MarkerCluster(name='States View')
    district_cluster = MarkerCluster(name='Districts View')
    station_cluster = MarkerCluster(name='Police Stations View')

    # Process state-level data
    state_stats = df.groupby('State/UT Name').agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum'
    }).reset_index()

    # Process district-level data
    district_stats = df.groupby(['State/UT Name', 'District']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum'
    }).reset_index()

    # Process police station-level data
    station_stats = df.groupby(['State/UT Name', 'District', 'Police Station']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum',
        'Category': lambda x: ', '.join(set(x))
    }).reset_index()

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

    # Add markers using cached coordinates
    print("Adding state-level markers...")
    for _, row in state_stats.iterrows():
        location_string = f"{row['State/UT Name']}, India"
        lat, lon = get_cached_coordinates(location_string, conn)
        if lat and lon:
            popup_content = f"""
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}
            """
            folium.CircleMarker(
                location=[lat, lon],
                radius=20,
                popup=folium.Popup(popup_content, max_width=300),
                color=get_color(row['Fraudulent Amount']),
                fill=True,
                fill_opacity=0.7
            ).add_to(state_cluster)

    print("Adding district-level markers...")
    for _, row in district_stats.iterrows():
        location_string = f"{row['District']}, {row['State/UT Name']}, India"
        lat, lon = get_cached_coordinates(location_string, conn)
        if lat and lon:
            popup_content = f"""
                <b>District:</b> {row['District']}<br>
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}
            """
            folium.CircleMarker(
                location=[lat, lon],
                radius=15,
                popup=folium.Popup(popup_content, max_width=300),
                color=get_color(row['Fraudulent Amount']),
                fill=True,
                fill_opacity=0.7
            ).add_to(district_cluster)

    print("Adding police station-level markers...")
    heat_data = []
    for _, row in station_stats.iterrows():
        location_string = f"{row['Police Station']}, {row['District']}, {row['State/UT Name']}, India"
        lat, lon = get_cached_coordinates(location_string, conn)
        if lat and lon:
            popup_content = f"""
                <b>Police Station:</b> {row['Police Station']}<br>
                <b>District:</b> {row['District']}<br>
                <b>State:</b> {row['State/UT Name']}<br>
                <b>Total Cases:</b> {row['S No.']}<br>
                <b>Total Fraudulent Amount:</b> ₹{row['Fraudulent Amount']:,.2f}<br>
                <b>Categories:</b> {row['Category']}
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_content, max_width=300),
                icon=folium.Icon(color=get_color(row['Fraudulent Amount']))
            ).add_to(station_cluster)
            heat_data.append([lat, lon, row['S No.']])

    # Add heatmap layer
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
    
    conn.close()

if __name__ == "__main__":
    create_crime_map('crime_data.csv')
