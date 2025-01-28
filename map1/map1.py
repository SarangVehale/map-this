import folium

# Define a list of locations with latitude, longitude, and labels
locations = [
    {"lat": 37.7749, "long": -122.4194, "name": "San Francisco"},
    {"lat": 34.0522, "long": -118.2437, "name": "Los Angeles"},
    {"lat": 40.7128, "long": -74.0060, "name": "New York"}
]

# Create a Folium map centered at the first location
m = folium.Map(location=[locations[0]["lat"], locations[0]["long"]], zoom_start=5)

# Add markers for each location
for loc in locations:
    folium.Marker(
        location=[loc["lat"], loc["long"]],  # Latitude and longitude
        popup=loc["name"],  # Popup text when clicking the marker
        tooltip=f"Click for info on {loc['name']}"  # Tooltip text
    ).add_to(m)

# Display the map in the notebook (if using Jupyter) or save it to an HTML file
m.save("map_with_points.html")
print("Map with points saved as 'map_with_points.html'. Open this file in a browser to view the map.")

