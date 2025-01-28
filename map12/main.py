import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import warnings
import os
warnings.filterwarnings('ignore')

def validate_files(required_files):
    """Validate that all required GADM files exist"""
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    if missing_files:
        raise FileNotFoundError(f"Missing required files: {', '.join(missing_files)}")

def load_gadm_layers():
    """Load GADM administrative boundary layers"""
    try:
        # Define the files we need
        files = {
            'country': 'gadm41_IND_0.shp',
            'state': 'gadm41_IND_1.shp',
            'district': 'gadm41_IND_2.shp',
            'subdistrict': 'gadm41_IND_3.shp'
        }
        
        # Validate files exist
        validate_files(files.values())
        
        # Load the layers
        layers = {}
        for key, file in files.items():
            layers[key] = gpd.read_file(file)
            print(f"Loaded {key} layer with {len(layers[key])} features")
            
        return layers
    except Exception as e:
        print(f"Error loading GADM layers: {e}")
        return None

def process_csv(csv_file):
    """Process the CSV file and extract location information"""
    try:
        # Read CSV file
        df = pd.read_csv(csv_file)
        
        # Create a GeoDataFrame for police stations
        police_stations = df[['State/UT Name', 'District', 'Police Station']].drop_duplicates()
        print(f"Extracted {len(police_stations)} unique police stations")
        
        return police_stations
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return None

def create_map(layers, police_stations):
    """Create a map with administrative boundaries and police stations"""
    try:
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(20, 20))
        
        # Plot administrative boundaries
        layers['country'].boundary.plot(ax=ax, linewidth=2, color='black', label='Country Border')
        layers['state'].boundary.plot(ax=ax, linewidth=1.5, color='blue', label='State Border')
        layers['district'].boundary.plot(ax=ax, linewidth=0.5, color='gray', label='District Border')
        
        # Create a color map for states
        unique_states = police_stations['State/UT Name'].unique()
        colors = plt.cm.Set3(np.linspace(0, 1, len(unique_states)))
        state_colors = dict(zip(unique_states, colors))
        
        # Plot police stations
        for idx, row in police_stations.iterrows():
            # Find the district geometry
            district_mask = layers['district']['NAME_2'] == row['District']
            if district_mask.any():
                district_geom = layers['district'][district_mask].geometry.iloc[0]
                # Use the centroid of the district for the police station
                centroid = district_geom.centroid
                ax.plot(centroid.x, centroid.y, 'ro', markersize=5, 
                       color=state_colors[row['State/UT Name']])
                ax.annotate(row['Police Station'], 
                          (centroid.x, centroid.y),
                          xytext=(5, 5), 
                          textcoords='offset points',
                          fontsize=8,
                          bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))
        
        # Customize the plot
        plt.title('Police Stations Map of India', fontsize=16, pad=20)
        
        # Add legend for states
        legend_elements = [plt.Line2D([0], [0], marker='o', color='w', 
                                    markerfacecolor=color, label=state,
                                    markersize=10)
                         for state, color in state_colors.items()]
        ax.legend(handles=legend_elements, 
                 title='States/UTs',
                 loc='center left',
                 bbox_to_anchor=(1, 0.5))
        
        # Remove axes
        ax.axis('off')
        
        # Adjust layout to prevent cutting off
        plt.tight_layout()
        
        return fig
    except Exception as e:
        print(f"Error creating map: {e}")
        return None

def save_map(fig, output_file='police_stations_map.png'):
    """Save the map to a file"""
    try:
        fig.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Map saved as {output_file}")
    except Exception as e:
        print(f"Error saving map: {e}")

def main(csv_file):
    """Main function to orchestrate the mapping process"""
    print("Starting the mapping process...")
    
    # Load GADM layers
    print("Loading GADM layers...")
    layers = load_gadm_layers()
    if layers is None:
        return
    
    # Process CSV file
    print("Processing CSV file...")
    police_stations = process_csv(csv_file)
    if police_stations is None:
        return
    
    # Create map
    print("Creating map...")
    fig = create_map(layers, police_stations)
    if fig is None:
        return
    
    # Save map
    print("Saving map...")
    save_map(fig)
    
    print("Mapping process completed successfully!")

if __name__ == "__main__":
    import numpy as np
    
    # Create a sample CSV if none provided
    sample_data = '''S No.,Acknowledgement No.,Name of Complainant,Mobile No. of Complainant,State/UT Name,Crime Aditional Information,District,Police Station,Category,Sub Category,Suspected Mobile No,Reported URL,Status,Incident Date,Complaint Date,Fraudulent Amount,Lien Amount,Last Action Taken on
1,ABC123,John Doe,1234567890,Maharashtra,Theft,Mumbai,Colaba,Property,Theft,9876543210,,,2023-01-01,2023-01-02,10000,0,2023-01-03
2,DEF456,Jane Smith,2345678901,Delhi,Fraud,Central Delhi,Connaught Place,Cyber,Fraud,8765432109,,,2023-01-02,2023-01-03,20000,0,2023-01-04'''

    # Save sample data
    with open('sample_crime_data.csv', 'w') as f:
        f.write(sample_data)
    
    # Run the main function
    main('sample_crime_data.csv')
