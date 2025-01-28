import folium
import csv
import argparse
import os
from geopy.distance import geodesic

# Function to load coordinates from a file
def load_coordinates_from_file(file_path):
    locations = []
    try:
        with open(file_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                lat = float(row['Latitude'])
                long = float(row['Longitude'])
                name = row.get('Name', 'Unknown Location')
                locations.append({"lat": lat, "long": long, "name": name})
        return locations
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

# Function to get user input for coordinates
def get_user_coordinates():
    locations = []
    num_locations = int(input("How many locations do you want to add? "))
    for i in range(num_locations):
        print(f"\nEnter details for location {i + 1}:")
        lat = float(input("  Latitude: "))
        long = float(input("  Longitude: "))
        name = input("  Name or Description: ")
        locations.append({"lat": lat, "long": long, "name": name})
    return locations

# Function to calculate distances and draw lines between locations
def add_distance_lines(map_obj, locations):
    for i in range(len(locations) - 1):
        loc1 = (locations[i]["lat"], locations[i]["long"])
        loc2 = (locations[i + 1]["lat"], locations[i + 1]["long"])
        distance = geodesic(loc1, loc2).kilometers

        # Add a line between the locations
        folium.PolyLine([loc1, loc2], color="blue", weight=2.5, opacity=0.8).add_to(map_obj)

        # Add a marker in the middle of the line to show the distance
        mid_lat = (locations[i]["lat"] + locations[i + 1]["lat"]) / 2
        mid_long = (locations[i]["long"] + locations[i + 1]["long"]) / 2
        folium.Marker(
            location=[mid_lat, mid_long],
            popup=f"{distance:.2f} km",
            tooltip=f"Distance: {distance:.2f} km",
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(map_obj)

# Function to prompt the user to choose an input method
def select_input_method():
    print("\nSelect input method:")
    print("1. Provide a file (choose at runtime)")
    print("2. Enter coordinates manually")
    print("3. Exit program")
    choice = int(input("Enter your choice (1/2/3): "))
    return choice

# Main function
def main():
    parser = argparse.ArgumentParser(description="Generate a map with markers and distances.")
    parser.add_argument('--file', type=str, help="Path to the CSV file containing coordinates.")
    args = parser.parse_args()

    locations = []

    # If a file is provided as a command-line argument
    if args.file:
        print(f"Loading coordinates from file: {args.file}")
        locations = load_coordinates_from_file(args.file)

    # If no file argument is provided, prompt the user to choose an input method
    else:
        while not locations:
            method = select_input_method()

            if method == 1:
                file_path = input("Enter the path to the CSV file: ")
                if os.path.exists(file_path):
                    locations = load_coordinates_from_file(file_path)
                else:
                    print(f"File '{file_path}' does not exist. Try again.")
            elif method == 2:
                locations = get_user_coordinates()
            elif method == 3:
                print("Exiting program.")
                return
            else:
                print("Invalid choice. Please select 1, 2, or 3.")

    if not locations:
        print("No valid locations were provided. Exiting program.")
        return

    # Create a Folium map centered at the first location
    m = folium.Map(location=[locations[0]["lat"], locations[0]["long"]], zoom_start=5)

    # Add markers for each location
    for loc in locations:
        folium.Marker(
            location=[loc["lat"], loc["long"]],
            popup=loc["name"],
            tooltip=f"Click for info on {loc['name']}"
        ).add_to(m)

    # Add distance lines and calculate distances
    if len(locations) > 1:
        add_distance_lines(m, locations)

    # Save the map to an HTML file
    m.save("map_with_distances.html")
    print("\nMap with distances saved as 'map_with_distances.html'. Open this file in a browser to view the map.")

if __name__ == "__main__":
    main()

