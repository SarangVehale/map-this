import pandas as pd
import sqlite3
import json
from pathlib import Path
import hashlib
import sys
import logging

# Configure logging
logging.basicConfig(
    filename='map_creation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_database():
    """Check if database exists and has correct structure"""
    try:
        conn = sqlite3.connect('locations.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='locations';
        """)
        
        if not cursor.fetchone():
            print("Error: Database exists but 'locations' table is missing.")
            print("Please run the preprocessing script first.")
            sys.exit(1)
            
        cursor.execute("PRAGMA table_info(locations)")
        columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            'location_hash', 'location_string', 'latitude', 
            'longitude', 'success'
        }
        
        if not required_columns.issubset(columns):
            print("Error: Database table structure is incorrect.")
            print("Please run the preprocessing script again.")
            sys.exit(1)
            
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print("Please run the preprocessing script first.")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

def get_color(amount):
    """Return color based on amount"""
    if amount > 1000000:
        return 'red'
    elif amount > 100000:
        return 'orange'
    elif amount > 10000:
        return 'yellow'
    return 'green'

def get_coordinates(location_string, cursor):
    """Get coordinates from database"""
    try:
        location_hash = hashlib.md5(location_string.encode()).hexdigest()
        cursor.execute("""
            SELECT latitude, longitude 
            FROM locations 
            WHERE location_hash = ? AND success = 1
        """, (location_hash,))
        result = cursor.fetchone()
        return result if result else (None, None)
    except sqlite3.Error as e:
        logging.error(f"Database error while getting coordinates: {e}")
        return None, None

def generate_map_html(df, here_api_key):
    """Generate HTML file with HERE Maps visualization"""
    # Prepare the statistics
    print("Preparing statistics...")
    state_stats = df.groupby('State/UT Name').agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum',
        'Category': lambda x: ', '.join(set(x))
    }).reset_index()
    
    district_stats = df.groupby(['State/UT Name', 'District']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum',
        'Category': lambda x: ', '.join(set(x))
    }).reset_index()
    
    station_stats = df.groupby(['State/UT Name', 'District', 'Police Station']).agg({
        'S No.': 'count',
        'Fraudulent Amount': 'sum',
        'Category': lambda x: ', '.join(set(x))
    }).reset_index()
    
    # Connect to database
    conn = sqlite3.connect('locations.db')
    cursor = conn.cursor()
    
    print("Generating HTML...")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="initial-scale=1.0, width=device-width" />
        <title>Crime Map Visualization</title>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-core.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-service.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-ui.js"></script>
        <script src="https://js.api.here.com/v3/3.1/mapsjs-mapevents.js"></script>
        <link rel="stylesheet" type="text/css" href="https://js.api.here.com/v3/3.1/mapsjs-ui.css" />
        <style>
            body {{ margin: 0; padding: 0; }}
            #mapContainer {{ height: 100vh; width: 100%; }}
            .H_ib_content {{ max-width: 400px; }}
            .legend {{
                position: fixed;
                bottom: 20px;
                left: 20px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 1000;
                font-family: Arial, sans-serif;
            }}
            .info-panel {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 1000;
                font-family: Arial, sans-serif;
            }}
            .current-view {{
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: white;
                padding: 10px 20px;
                border-radius: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                z-index: 1000;
                font-family: Arial, sans-serif;
                font-weight: bold;
            }}
            .stats-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}
            .stats-table th, .stats-table td {{
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
        </style>
    </head>
    <body>
        <div id="mapContainer"></div>
        <div id="currentView" class="current-view">State View</div>
        <div class="legend">
            <h4 style="margin-top: 0;">Crime Amount Range</h4>
            <div><span style="color: red; font-size: 20px;">●</span> High (>₹10,00,000)</div>
            <div><span style="color: orange; font-size: 20px;">●</span> Medium (₹1,00,000-10,00,000)</div>
            <div><span style="color: yellow; font-size: 20px;">●</span> Low (₹10,000-1,00,000)</div>
            <div><span style="color: green; font-size: 20px;">●</span> Very Low (<₹10,000)</div>
        </div>
        <div class="info-panel">
            <h4 style="margin-top: 0;">Zoom Levels</h4>
            <div>Zoom 5-6: State view</div>
            <div>Zoom 7-8: District view</div>
            <div>Zoom 9+: Police Station view</div>
        </div>
        <script>
            function initializeMap() {{
                var platform = new H.service.Platform({{
                    apikey: '{here_api_key}'
                }});

                var defaultLayers = platform.createDefaultLayers();
                
                var map = new H.Map(
                    document.getElementById('mapContainer'),
                    defaultLayers.vector.normal.map,
                    {{
                        zoom: 5,
                        center: {{ lat: 20.5937, lng: 78.9629 }},
                        pixelRatio: window.devicePixelRatio || 1
                    }}
                );

                window.addEventListener('resize', () => map.getViewPort().resize());

                var behavior = new H.mapevents.Behavior(new H.mapevents.MapEvents(map));
                var ui = H.ui.UI.createDefault(map, defaultLayers);

                var stateGroup = new H.map.Group();
                var districtGroup = new H.map.Group();
                var stationGroup = new H.map.Group();

                function formatCurrency(amount) {{
                    return '₹' + amount.toLocaleString('en-IN', {{
                        maximumFractionDigits: 2,
                        minimumFractionDigits: 2
                    }});
                }}

                function createInfoBubble(evt, data, level) {{
                    var content = '<div style="padding: 15px;">';
                    
                    if (level === 'state') {{
                        content += `
                            <h3>${{data.state}}</h3>
                            <table class="stats-table">
                                <tr><th>Total Cases</th><td>${{data.cases}}</td></tr>
                                <tr><th>Total Amount</th><td>${{formatCurrency(data.amount)}}</td></tr>
                                <tr><th>Categories</th><td>${{data.categories}}</td></tr>
                            </table>
                        `;
                    }} else if (level === 'district') {{
                        content += `
                            <h3>${{data.district}}</h3>
                            <table class="stats-table">
                                <tr><th>State</th><td>${{data.state}}</td></tr>
                                <tr><th>Total Cases</th><td>${{data.cases}}</td></tr>
                                <tr><th>Total Amount</th><td>${{formatCurrency(data.amount)}}</td></tr>
                                <tr><th>Categories</th><td>${{data.categories}}</td></tr>
                            </table>
                        `;
                    }} else {{
                        content += `
                            <h3>${{data.station}}</h3>
                            <table class="stats-table">
                                <tr><th>District</th><td>${{data.district}}</td></tr>
                                <tr><th>State</th><td>${{data.state}}</td></tr>
                                <tr><th>Total Cases</th><td>${{data.cases}}</td></tr>
                                <tr><th>Total Amount</th><td>${{formatCurrency(data.amount)}}</td></tr>
                                <tr><th>Categories</th><td>${{data.categories}}</td></tr>
                            </table>
                        `;
                    }}
                    
                    content += '</div>';
                    
                    var bubble = new H.ui.InfoBubble(evt.target.getGeometry(), {{
                        content: content
                    }});
                    
                    ui.addBubble(bubble);
                }}

                // Add markers
                {generate_markers_js(state_stats, district_stats, station_stats, cursor)}

                map.addObject(stateGroup);
                map.addObject(districtGroup);
                map.addObject(stationGroup);

                map.addEventListener('mapviewchange', function() {{
                    var zoom = map.getZoom();
                    var currentView = document.getElementById('currentView');
                    
                    if (zoom < 7) {{
                        stateGroup.setVisibility(true);
                        districtGroup.setVisibility(false);
                        stationGroup.setVisibility(false);
                        currentView.textContent = 'State View';
                    }} else if (zoom < 9) {{
                        stateGroup.setVisibility(false);
                        districtGroup.setVisibility(true);
                        stationGroup.setVisibility(false);
                        currentView.textContent = 'District View';
                    }} else {{
                        stateGroup.setVisibility(false);
                        districtGroup.setVisibility(false);
                        stationGroup.setVisibility(true);
                        currentView.textContent = 'Police Station View';
                    }}
                }});

                // Initial visibility
                var initialZoom = map.getZoom();
                if (initialZoom < 7) {{
                    stateGroup.setVisibility(true);
                    districtGroup.setVisibility(false);
                    stationGroup.setVisibility(false);
                }} else if (initialZoom < 9) {{
                    stateGroup.setVisibility(false);
                    districtGroup.setVisibility(true);
                    stationGroup.setVisibility(false);
                }} else {{
                    stateGroup.setVisibility(false);
                    districtGroup.setVisibility(false);
                    stationGroup.setVisibility(true);
                }}
            }}

            window.onload = initializeMap;
        </script>
    </body>
    </html>
    """
    
    def generate_markers_js(state_stats, district_stats, station_stats, cursor):
        """Generate JavaScript code for markers"""
        markers_js = []
        
        # Add state markers
        for _, row in state_stats.iterrows():
            lat, lon = get_coordinates(f"{row['State/UT Name']}, India", cursor)
            if lat and lon:
                data = {
                    'state': row['State/UT Name'],
                    'cases': int(row['S No.']),
                    'amount': float(row['Fraudulent Amount']),
                    'categories': row['Category']
                }
                
                markers_js.append(f"""
                    var marker = new H.map.Circle(
                        {{lat: {lat}, lng: {lon}}},
                        50000,
                        {{
                            style: {{
                                fillColor: '{get_color(row["Fraudulent Amount"])}',
                                strokeColor: 'black',
                                lineWidth: 2,
                                fillOpacity: 0.6
                            }}
                        }}
                    );
                    
                    marker.addEventListener('tap', function(evt) {{
                        createInfoBubble(evt, {json.dumps(data)}, 'state');
                    }});
                    
                    stateGroup.addObject(marker);
                """)
        
        # Add district markers
        for _, row in district_stats.iterrows():
            lat, lon = get_coordinates(f"{row['District']}, {row['State/UT Name']}, India", cursor)
            if lat and lon:
                data = {
                    'district': row['District'],
                    'state': row['State/UT Name'],
                    'cases': int(row['S No.']),
                    'amount': float(row['Fraudulent Amount']),
                    'categories': row['Category']
                }
                
                markers_js.append(f"""
                    var marker = new H.map.Circle(
                        {{lat: {lat}, lng: {lon}}},
                        25000,
                        {{
                            style: {{
                                fillColor: '{get_color(row["Fraudulent Amount"])}',
                                strokeColor: 'black',
                                lineWidth: 2,
                                fillOpacity: 0.6
                            }}
                        }}
                    );
                    
                    marker.addEventListener('tap', function(evt) {{
                        createInfoBubble(evt, {json.dumps(data)}, 'district');
                    }});
                    
                    districtGroup.addObject(marker);
                """)
        
        # Add police station markers
        for _, row in station_stats.iterrows():
            lat, lon = get_coordinates(f"{row['Police Station']}, {row['District']}, {row['State/UT Name']}, India", cursor)
            if lat and lon:
                data = {
                    'station': row['Police Station'],
                    'district': row['District'],
                    'state': row['State/UT Name'],
                    'cases': int(row['S No.']),
                    'amount': float(row['Fraudulent Amount']),
                    'categories': row['Category']
                }
                
                markers_js.append(f"""
                    var marker = new H.map.Circle(
                        {{lat: {lat}, lng: {lon}}},
                        10000,
                        {{
                            style: {{
                                fillColor: '{get_color(row["Fraudulent Amount"])}',
                                strokeColor: 'black',
                                lineWidth: 2,
                                fillOpacity: 0.6
                            }}
                        }}
                    );
                    
                    marker.addEventListener('tap', function(evt) {{
                        createInfoBubble(evt, {json.dumps(data)}, 'station');
                    }});
                    
                    stationGroup.addObject(marker);
                """)
        
        return '\n'.join(markers_js)
    
    # Generate the HTML file
    print("Writing HTML file...")
    with open('crime_map.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("Map has been created as 'crime_map.html'")
    conn.close()

def load_data(csv_file):
    """Load and process CSV data"""
    try:
        df = pd.read_csv(csv_file)
        
        required_columns = ['State/UT Name', 'District', 'Police Station', 'S No.', 'Fraudulent Amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Error: Missing required columns: {', '.join(missing_columns)}")
            sys.exit(1)
            
        df['Fraudulent Amount'] = pd.to_numeric(df['Fraudulent Amount'], errors='coerce').fillna(0)
        
        return df
        
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print("Error: CSV file is empty.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        sys.exit(1)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Create crime map using HERE Maps')
    parser.add_argument('--csv', required=True, help='Input CSV file')
    parser.add_argument('--api-key', required=True, help='HERE Maps API key')
    args = parser.parse_args()
    
    print("Checking database...")
    check_database()
    
    print("Loading data...")
    df = load_data(args.csv)
    
    print("Generating map...")
    generate_map_html(df, args.api_key)

if __name__ == "__main__":
    main()
