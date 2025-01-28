import sqlite3
import pandas as pd
import hashlib
import argparse


def get_coordinates(state, police_station, cursor):
    """Retrieve coordinates for a state and police station."""
    location_hash = hashlib.md5(f"{police_station}, {state}".encode()).hexdigest()
    cursor.execute(
        "SELECT latitude, longitude FROM locations WHERE location_hash = ? AND success = 1",
        (location_hash,)
    )
    result = cursor.fetchone()
    return result if result else (None, None)


def generate_map_html(csv_file, here_api_key, db_path="locations.db"):
    """Generate a crime map using cached coordinates."""
    # Load data
    df = pd.read_csv(csv_file)

    # Aggregate crime statistics
    state_stats = df.groupby("State/UT Name").size().reset_index(name="Total Crimes")
    station_stats = df.groupby(["State/UT Name", "Police Station"]).size().reset_index(name="Total Crimes")

    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create map HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crime Map</title>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-core.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-service.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-ui.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-mapevents.js"></script>
        <link rel="stylesheet" type="text/css" href="https://js.api.here.com/v3/3.1/mapsjs-ui.css" />
        <style>
            body {{ margin: 0; padding: 0; }}
            #mapContainer {{ height: 100vh; width: 100%; }}
        </style>
    </head>
    <body>
        <div id="mapContainer"></div>
        <script>
            function initializeMap() {{
                var platform = new H.service.Platform({{
                    apikey: '{here_api_key}'
                }});
                var maptypes = platform.createDefaultLayers();
                var map = new H.Map(
                    document.getElementById('mapContainer'),
                    maptypes.vector.normal.map,
                    {{
                        zoom: 5,
                        center: {{ lat: 20.5937, lng: 78.9629 }}
                    }}
                );
                var ui = H.ui.UI.createDefault(map, maptypes);
                var markersGroup = new H.map.Group();
                
                function addMarker(lat, lon, label) {{
                    var marker = new H.map.Marker({{ lat: lat, lng: lon }});
                    marker.setData(label);
                    marker.addEventListener('tap', function(evt) {{
                        var bubble = new H.ui.InfoBubble(evt.target.getGeometry(), {{
                            content: evt.target.getData()
                        }});
                        ui.addBubble(bubble);
                    }});
                    markersGroup.addObject(marker);
                }}
    """

    # Add state markers
    for _, row in state_stats.iterrows():
        lat, lon = get_coordinates(row["State/UT Name"], "", cursor)
        if lat and lon:
            html_content += f"""
            addMarker({lat}, {lon}, "<b>{row['State/UT Name']}</b><br>Total Crimes: {row['Total Crimes']}");
            """

    # Add police station markers
    for _, row in station_stats.iterrows():
        lat, lon = get_coordinates(row["State/UT Name"], row["Police Station"], cursor)
        if lat and lon:
            html_content += f"""
            addMarker({lat}, {lon}, "<b>{row['Police Station']}</b><br>State: {row['State/UT Name']}<br>Total Crimes: {row['Total Crimes']}");
            """

    html_content += """
                map.addObject(markersGroup);
            }
            window.onload = initializeMap;
        </script>
    </body>
    </html>
    """

    # Save HTML file
    with open("crime_map.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Map has been created as 'crime_map.html'")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate crime map.")
    parser.add_argument("--csv", required=True, help="Input CSV file")
    parser.add_argument("--api-key", required=True, help="HERE Maps API key")
    args = parser.parse_args()

    generate_map_html(args.csv, args.api_key)

