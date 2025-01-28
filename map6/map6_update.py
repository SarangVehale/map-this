import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Initialize geolocator with caching and progress bar
geolocator = Nominatim(user_agent="optimized_crime_map_app", timeout=10)
geo_cache = {}

def get_coordinates_with_cache(state, district, police_station):
    """Get coordinates of a location with caching."""
    key = f"{police_station}, {district}, {state}"
    if key in geo_cache:
        return geo_cache[key]
    try:
        location = geolocator.geocode(key)
        if location:
            geo_cache[key] = (location.latitude, location.longitude)
            return location.latitude, location.longitude
    except Exception as e:
        print(f"Error fetching coordinates for {key}: {e}")
    return None, None

# Load data
csv_file = "/home/i4c/Downloads/data/Additional_Information _ 03_09_2024 10_19_03.csv"  # Replace with your CSV file path
data = pd.read_csv(csv_file)

# Filter relevant columns
required_columns = ['State/UT Name', 'District', 'Police Station', 'Fraudulent Amount']
if not set(required_columns).issubset(data.columns):
    raise ValueError(f"CSV file must contain these columns: {required_columns}")

filtered_data = data[required_columns].dropna()

# Add progress bar
tqdm.pandas()

def fetch_coordinates(row):
    return get_coordinates_with_cache(row['State/UT Name'], row['District'], row['Police Station'])

# Apply multithreading for geocoding
print("Fetching coordinates...")
with ThreadPoolExecutor(max_workers=5) as executor:
    coordinates = list(tqdm(executor.map(fetch_coordinates, filtered_data.to_dict('records')), total=len(filtered_data)))

filtered_data['Latitude'], filtered_data['Longitude'] = zip(*coordinates)
filtered_data = filtered_data.dropna(subset=['Latitude', 'Longitude'])

# Aggregate fraudulent amounts by state for zoom-out view
state_fraud_totals = filtered_data.groupby('State/UT Name')['Fraudulent Amount'].sum().to_dict()

# Create the map
crime_map = folium.Map(location=[20.5937, 78.9629], zoom_start=5)  # Centered on India
marker_cluster = MarkerCluster().add_to(crime_map)

# Add police station markers
for _, row in filtered_data.iterrows():
    folium.Marker(
        location=[row['Latitude'], row['Longitude']],
        popup=(
            f"<b>Police Station:</b> {row['Police Station']}<br>"
            f"<b>District:</b> {row['District']}<br>"
            f"<b>State:</b> {row['State/UT Name']}<br>"
            f"<b>Fraudulent Amount:</b> ₹{row['Fraudulent Amount']}"
        ),
        tooltip=f"{row['Police Station']} (₹{row['Fraudulent Amount']})",
    ).add_to(marker_cluster)

# Add state-level fraudulent amount data (for zoom-out view)
for state, total_fraud in state_fraud_totals.items():
    try:
        state_location = geolocator.geocode(f"{state}, India")
        if state_location:
            folium.Marker(
                location=[state_location.latitude, state_location.longitude],
                popup=(
                    f"<b>State:</b> {state}<br>"
                    f"<b>Total Fraudulent Amount:</b> ₹{total_fraud}"
                ),
                icon=folium.DivIcon(html=f"<div style='font-size: 12px; color: red;'>{state}: ₹{total_fraud}</div>"),
            ).add_to(crime_map)
    except Exception as e:
        print(f"Error fetching state data for {state}: {e}")

# Save the map
crime_map.save("crime_map.html")
print("Map has been generated and saved as 'crime_map.html'. Open it in a browser to view.")

