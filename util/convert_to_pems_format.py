import numpy as np
import pandas as pd
import geopandas as gpd
import os
import networkx as nx
from pathlib import Path
from tqdm import tqdm
from shapely.geometry import Point, LineString

def convert_to_pems_format(city_name, output_dir=None):
    """
    Convert city traffic data to PEMS-like format
    
    Parameters:
    - city_name: name of the city
    - output_dir: output directory, defaults to "data/debug/pems_format/{city_name}"
    
    Outputs:
    - {city_name}_distance.csv: CSV file containing from_node, to_node, distance columns
    - {city_name}_data.npz: NPZ file containing flow, speed, occupancy
    """
    # Set paths
    if output_dir is None:
        output_dir = f"data/debug/pems_format/{city_name}"
    
    input_path = f"data/debug/IUTFD/{city_name}/npz/{city_name}_traffic_network.npz"
    geojson_path = f"data/debug/input/{city_name}/selected_network_4326.geojson"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Processing data for city {city_name}...")
    
    # Load NPZ data
    try:
        data = np.load(input_path, allow_pickle=True)
        print(f"Successfully loaded {input_path}")
    except Exception as e:
        print(f"Failed to load data: {str(e)}")
        return
    
    # Get sensor data
    if 'sensor_flow' in data.files and 'sensor_speed' in data.files and 'sensor_occ' in data.files:
        sensor_flow = data['sensor_flow']  # flow data
        sensor_speed = data['sensor_speed']  # speed data
        sensor_occ = data['sensor_occ']  # occupancy data
        
        # Check data dimensions
        print(f"Sensor flow data shape: {sensor_flow.shape}")
        print(f"Sensor speed data shape: {sensor_speed.shape}")
        print(f"Sensor occupancy data shape: {sensor_occ.shape}")
        
        # Get timestamps and sensor IDs
        timestamps = data['timestamps'] if 'timestamps' in data.files else None
        sensor_ids = data['sensor_road_ids'] if 'sensor_road_ids' in data.files else None
        
        if timestamps is not None:
            print(f"Number of timestamps: {len(timestamps)}")
            print(f"Sample timestamps: {timestamps[:3]}")
        
        if sensor_ids is not None:
            print(f"Number of sensors: {len(sensor_ids)}")
            print(f"Sample sensor IDs: {sensor_ids[:5]}")
        
        # Get road length information
        road_lengths = {}
        
        if 'sensor_attributes' in data.files and data['sensor_attributes'].size > 0:
            sensor_attr = data['sensor_attributes'].item() if hasattr(data['sensor_attributes'], 'item') else data['sensor_attributes']
            if isinstance(sensor_attr, dict) and 'road_length' in sensor_attr and 'road_id' in sensor_attr:
                for i, road_id in enumerate(sensor_attr['road_id']):
                    road_lengths[road_id] = float(sensor_attr['road_length'][i])
                print(f"Loaded {len(road_lengths)} road length records from sensor_attributes")
        
        # Get network attributes (may contain more roads)
        if 'network_attributes' in data.files and data['network_attributes'].size > 0:
            network_attr = data['network_attributes'].item() if hasattr(data['network_attributes'], 'item') else data['network_attributes']
            if isinstance(network_attr, dict) and 'road_length' in network_attr and 'road_id' in network_attr:
                for i, road_id in enumerate(network_attr['road_id']):
                    if road_id not in road_lengths:  # Avoid overwriting sensor road lengths
                        road_lengths[road_id] = float(network_attr['road_length'][i])
                print(f"Loaded more road length information from network_attributes, {len(road_lengths)} total")
        
        # Convert sensor IDs to set for fast lookup
        sensor_id_set = set(map(int, sensor_ids))
        
        # Use full GeoJSON data to create road network
        try:
            # Load GeoJSON data
            if os.path.exists(geojson_path):
                print(f"Loading GeoJSON data: {geojson_path}")
                roads_gdf = gpd.read_file(geojson_path)
                print(f"GeoJSON data shape: {roads_gdf.shape}")
                print(f"GeoJSON data columns: {roads_gdf.columns.tolist()}")
                
                # Create network graph
                G, all_road_ids, road_length_dict = create_road_network_from_geojson(roads_gdf)
                print(f"Created network with {len(all_road_ids)} roads")
                
                # Create connections
                print("Extracting connections from road network graph...")
                connections = []
                for u, v, data in G.edges(data=True):
                    # Directly use road_length from GeoJSON instead of calculating distance
                    from_length = road_length_dict.get(u, 50.0)
                    to_length = road_length_dict.get(v, 50.0)
                    # For edges, use actual road length instead of calculated distance
                    distance = data.get('road_length', max(from_length, to_length))
                    
                    connections.append({
                        'from_node': u,
                        'to_node': v,
                        'distance': distance
                    })
                
                print(f"Created {len(connections)} road connections from GeoJSON")
                
                # Create data array containing all roads
                n_timestamps = len(timestamps) if timestamps is not None else sensor_flow.shape[0]
                n_roads = len(all_road_ids)
                
                print(f"Creating data array with shape ({n_timestamps}, {n_roads}, 3)...")
                
                # Create a mapping from road_id to index in all_road_ids
                road_id_to_index = {road_id: i for i, road_id in enumerate(all_road_ids)}
                
                # Create data array, initializing to -1 (indicating no sensor data)
                full_data = np.full((n_timestamps, n_roads, 3), -1, dtype=np.float32)
                
                # Fill actual data for roads with sensors
                for i, sensor_id in enumerate(sensor_ids):
                    int_sensor_id = int(sensor_id)
                    if int_sensor_id in road_id_to_index:
                        idx = road_id_to_index[int_sensor_id]
                        full_data[:, idx, 0] = sensor_flow[:, i]  # flow
                        full_data[:, idx, 1] = sensor_speed[:, i]  # speed
                        full_data[:, idx, 2] = sensor_occ[:, i]    # occupancy
                
                # Check how many roads have actual sensor data
                has_data_count = sum(1 for road_id in all_road_ids if road_id in sensor_id_set)
                print(f"Out of {n_roads} roads, {has_data_count} have sensor data")
                
                # Save connections and distance as CSV
                connections_df = pd.DataFrame(connections)
                distance_path = os.path.join(output_dir, f"{city_name}_distance.csv")
                connections_df.to_csv(distance_path, index=False)
                print(f"Distance data saved to: {distance_path}")
                
                # Save to NPZ format
                npz_path = os.path.join(output_dir, f"{city_name}_data.npz")
                np.savez_compressed(npz_path, data=full_data)
                print(f"Data saved to: {npz_path}")
                
                # Save metadata (including all road IDs)
                meta_data = {
                    "timestamps": timestamps,
                    "road_ids": np.array(all_road_ids),
                    "sensor_road_ids": sensor_ids,  # Keep original sensor IDs for reference
                }
                meta_path = os.path.join(output_dir, f"{city_name}_meta.npz")
                np.savez_compressed(meta_path, **meta_data)
                print(f"Metadata saved to: {meta_path}")
                
                print(f"{city_name} data conversion complete!")
                return
            else:
                print(f"GeoJSON file does not exist: {geojson_path}")
        except Exception as e:
            print(f"Error creating road network using GeoJSON: {str(e)}")
        
        # If GeoJSON processing fails, fallback to using only sensor data
        print("Falling back to using only sensor data...")
        
        # Create basic connections
        connections = create_connections_from_road_lengths(sensor_ids, road_lengths)
        
        # Save connections and distances to CSV
        connections_df = pd.DataFrame(connections)
        distance_path = os.path.join(output_dir, f"{city_name}_distance.csv")
        connections_df.to_csv(distance_path, index=False)
        print(f"Distance data saved to: {distance_path}")
        
        # Convert raw data to 3D array [timestamps, nodes, features]
        n_timestamps, n_sensors = sensor_flow.shape
        pems_data = np.zeros((n_timestamps, n_sensors, 3), dtype=np.float32)
        
        pems_data[:, :, 0] = sensor_flow  # flow
        pems_data[:, :, 1] = sensor_speed  # speed
        pems_data[:, :, 2] = sensor_occ    # occupancy
        
        # Save as NPZ format
        npz_path = os.path.join(output_dir, f"{city_name}_data.npz")
        np.savez_compressed(npz_path, data=pems_data)
        print(f"Data saved to: {npz_path}")
        
        # Save metadata
        if timestamps is not None:
            meta_data = {
                "timestamps": timestamps,
                "road_ids": sensor_ids,
            }
            meta_path = os.path.join(output_dir, f"{city_name}_meta.npz")
            np.savez_compressed(meta_path, **meta_data)
            print(f"Metadata saved to: {meta_path}")
        
        print(f"{city_name} data conversion complete! (using fallback method)")
    else:
        print("Missing required sensor data in data structure!")
        return

def create_road_network_from_geojson(roads_gdf):
    """
    Create network graph from GeoJSON road data
    
    Parameters:
    - roads_gdf: GeoDataFrame containing road geometry information
    
    Returns:
    - G: NetworkX graph object
    - all_road_ids: list of all road IDs
    - road_length_dict: mapping dictionary from road_id to length
    """
    print("Creating road network from GeoJSON...")
    
    # Create an empty undirected graph
    G = nx.Graph()
    
    # Check for required columns
    if 'road_id' not in roads_gdf.columns:
        # Try to find a possible ID column
        id_columns = [col for col in roads_gdf.columns if 'id' in col.lower()]
        if id_columns:
            print(f"Using {id_columns[0]} as road ID")
            roads_gdf['road_id'] = roads_gdf[id_columns[0]]
        else:
            print("Warning: road ID column does not exist, using index as ID")
            roads_gdf['road_id'] = range(len(roads_gdf))
    
    # Ensure road_id is integer type
    try:
        roads_gdf['road_id'] = roads_gdf['road_id'].astype(int)
    except:
        print("Warning: unable to convert road IDs to integers, using original values")
    
    # Check if road_length column exists
    if 'road_length' not in roads_gdf.columns:
        print("Warning: no road_length column in GeoJSON, will try to find other length columns")
        # Try finding a possible length column
        length_columns = [col for col in roads_gdf.columns if 'length' in col.lower()]
        if length_columns:
            print(f"Using {length_columns[0]} as road length")
            roads_gdf['road_length'] = roads_gdf[length_columns[0]]
        else:
            print("Warning: length column not found, will use geometric length")
            # Calculate geometric length (Note: might be inaccurate in EPSG:4326)
            roads_gdf['road_length'] = roads_gdf.geometry.length * 111000  # Rough conversion to meters
    
    # Create mapping from road ID to length
    road_length_dict = {}
    
    # Add roads as nodes
    all_road_ids = []
    for idx, row in tqdm(roads_gdf.iterrows(), total=len(roads_gdf), desc="Adding road nodes"):
        road_id = row['road_id']
        road_length = row['road_length']
        
        G.add_node(road_id, geometry=row.geometry, road_length=road_length)
        all_road_ids.append(road_id)
        road_length_dict[road_id] = road_length
    
    # Find intersecting roads and add as edges
    print("Finding intersecting roads...")
    # Create an R-tree spatial index to accelerate spatial queries
    sindex = roads_gdf.sindex
    
    # For each road, find other intersecting roads
    for idx, row in tqdm(roads_gdf.iterrows(), total=len(roads_gdf), desc="Finding road connections"):
        road_id = row['road_id']
        road_length = row['road_length']
        geom = row.geometry
        
        # Use spatial index to find possible matching roads
        possible_matches_idx = list(sindex.intersection(geom.bounds))
        possible_matches = roads_gdf.iloc[possible_matches_idx]
        
        # Filter out actual intersecting roads
        for idx2, row2 in possible_matches.iterrows():
            if idx == idx2:
                continue  # Skip self
                
            road_id2 = row2['road_id']
            road_length2 = row2['road_length']
            geom2 = row2.geometry
            
            if geom.intersects(geom2):
                # Use road_length directly as edge attribute, instead of calculating any distance
                # Use the longer of the two roads as the connection length
                edge_length = max(road_length, road_length2)
                
                # Add edge
                G.add_edge(road_id, road_id2, weight=edge_length, road_length=edge_length)
    
    print(f"Road network creation complete, with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    
    # Return graph, list of all road IDs, and road length dictionary
    return G, all_road_ids, road_length_dict

def create_connections_from_road_lengths(sensor_ids, road_lengths):
    """
    Create connections based on road lengths (fallback method)
    
    Using heuristic method: Roads with close IDs might be spatially close
    """
    print("Using fallback method to create road connections...")
    connections = []
    n_sensors = len(sensor_ids)
    
    # Create connections from each sensor to other sensors
    # Only connect sensors with similar IDs (as a simple spatial proximity heuristic)
    max_neighbor_distance = 5  # Only connect sensors with ID distance up to 5
    
    for i in range(n_sensors):
        source_id = int(sensor_ids[i])
        source_len = road_lengths.get(source_id, 50.0)  # Use default if no length info
        
        # Connect to nodes with nearby IDs
        for j in range(max(0, i-max_neighbor_distance), min(n_sensors, i+max_neighbor_distance+1)):
            if i == j:
                continue  # Skip self connection
            
            target_id = int(sensor_ids[j])
            target_len = road_lengths.get(target_id, 50.0)
            
            # Use the longer road as connection length
            distance = max(source_len, target_len)
            
            connections.append({
                'from_node': source_id,
                'to_node': target_id,
                'distance': distance
            })
    
    print(f"Fallback method created {len(connections)} road connections")
    return connections

def process_all_cities():
    """Process data for all available cities"""
    iutfd_dir = Path("data/debug/IUTFD")
    
    # Get all city directories
    city_dirs = [d for d in iutfd_dir.iterdir() if d.is_dir()]
    city_names = [d.name for d in city_dirs]
    
    print(f"Found {len(city_names)} cities")
    
    for city in city_names:
        try:
            # Check if NPZ file exists
            npz_file = iutfd_dir / city / "npz" / f"{city}_traffic_network.npz"
            if not npz_file.exists():
                print(f"Skipping {city} - {city}_traffic_network.npz not found")
                continue
            
            # Process city data
            convert_to_pems_format(city)
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")

if __name__ == "__main__":
    # Process a single city
    # convert_to_pems_format("augsburg")
    
    # Or process all cities
    process_all_cities() 