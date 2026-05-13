import os
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkb
import time

def convert_to_optimized_npz(city_folder):
    """
    Convert road network and sensor data to optimized npz format
    
    Method:
    1. Save complete network topology (all roads)
    2. Store sensor data separately (only roads with sensors)
    3. Establish mapping relationship (connecting complete network and sensor data)
    
    Parameters:
    - city_folder: path to the city data folder
    
    Returns:
    - Whether the conversion was successful
    """
    city_name = os.path.basename(city_folder)
    print(f"Converting data for {city_name}...")
    
    # File paths
    network_parquet = os.path.join(city_folder, "selected_network.parquet")
    readings_parquet = os.path.join(city_folder, "5min_readings.parquet")
    output_npz = os.path.join(city_folder, f"{city_name}_traffic_network.npz")
    
    # Check if files exist
    if not os.path.exists(network_parquet):
        print(f"Error: selected_network.parquet not found for {city_name}")
        return False
    
    if not os.path.exists(readings_parquet):
        print(f"Error: 5min_readings.parquet not found for {city_name}")
        return False
    
    try:
        start_time = time.time()
        
        # 1. Read road network data
        print("Reading road network data...")
        if "wkb" in pd.read_parquet(network_parquet, columns=None).columns:
            # If WKB column is included, convert back to geometry object
            df = pd.read_parquet(network_parquet)
            geometry = df['wkb'].apply(lambda x: wkb.loads(x) if x else None)
            network_df = gpd.GeoDataFrame(df.drop(columns=['wkb']), geometry=geometry)
        else:
            # Direct read
            network_df = pd.read_parquet(network_parquet)
        
        # Ensure road_id column exists, if not, try using other possible ID columns
        id_columns = ['road_id', 'id', 'edge_id', 'index']
        road_id_col = None
        for col in id_columns:
            if col in network_df.columns:
                road_id_col = col
                break
        
        if road_id_col is None:
            print("Warning: No road ID column found, creating sequential IDs")
            network_df['road_id'] = np.arange(len(network_df))
            road_id_col = 'road_id'
        
        # 2. Sort complete network by road_id
        print(f"Sorting complete network by {road_id_col}...")
        network_df = network_df.sort_values(by=road_id_col).reset_index(drop=True)
        
        # 3. Identify roads with sensors
        print("Identifying roads with sensors...")
        has_sensor_mask = network_df['detid'] != '-1'
        
        sensor_roads = network_df[has_sensor_mask].copy().reset_index(drop=True)
        print(f"Complete network: {len(network_df)} roads")
        print(f"Roads with sensors: {len(sensor_roads)}")
        
        # 4. Create mapping: complete network index -> sensor road index
        network_to_sensor = {}
        sensor_to_network = {}
        
        for i, (idx, road) in enumerate(sensor_roads.iterrows()):
            original_idx = network_df[network_df[road_id_col] == road[road_id_col]].index[0]
            network_to_sensor[original_idx] = i
            sensor_to_network[i] = original_idx
        
        # 5. Read sensor data
        print("Reading sensor data...")
        readings_df = pd.read_parquet(readings_parquet)
        
        # 6. Create mapping from sensor ID to sensor road index
        detid_to_sensor_idx = {}
        for i, (_, road) in enumerate(sensor_roads.iterrows()):
            detid_to_sensor_idx[road['detid']] = i
        
        # 7. Extract unique timestamps
        time_column = None
        for col in ['datetime', 'timestamp', 'time', 'date']:
            if col in readings_df.columns:
                time_column = col
                break
        
        if time_column is None:
            print("Error: No time column found in readings data")
            return False
        
        timestamps = sorted(readings_df[time_column].unique())
        print(f"Found {len(timestamps)} unique timestamps")
        
        # 8. Create sensor data matrix (timestamps x sensor roads)
        # Assume these metrics: flow, speed, occupancy
        data_columns = {}
        for col in ['flow', 'flow_sum', 'flow_mean_5min', 'speed', 'speed_mean', 'speed_weight', 'occ', 'occ_mean']:
            if col in readings_df.columns:
                data_columns[col] = readings_df.columns.get_loc(col)
        
        if not data_columns:
            print("Error: No valid data columns found in readings data")
            return False
        
        # Prepare arrays and time index mapping
        time_to_idx = {t: i for i, t in enumerate(timestamps)}
        n_times = len(timestamps)
        n_sensor_roads = len(sensor_roads)
        
        # Create array for each metric - only for roads with sensors
        data_arrays = {}
        for col_name in data_columns:
            data_arrays[col_name] = np.full((n_times, n_sensor_roads), np.nan, dtype=np.float32)
        
        # Fill data matrix
        print("Building data matrices...")
        for _, row in readings_df.iterrows():
            if row['detid'] in detid_to_sensor_idx:
                t_idx = time_to_idx.get(row[time_column])
                r_idx = detid_to_sensor_idx[row['detid']]
                
                if t_idx is not None:
                    for col_name, col_idx in data_columns.items():
                        if not pd.isna(row[col_name]):
                            data_arrays[col_name][t_idx, r_idx] = row[col_name]
        
        # 9. Prepare graph structure data
        adjacency_data = None
        if 'from_node' in network_df.columns and 'to_node' in network_df.columns:
            print("Building network connectivity...")
            # Create node ID mapping
            unique_nodes = set()
            for _, road in network_df.iterrows():
                unique_nodes.add(road['from_node'])
                unique_nodes.add(road['to_node'])
            
            node_to_idx = {node: i for i, node in enumerate(sorted(unique_nodes))}
            n_nodes = len(node_to_idx)
            
            # Create edge list
            edges = []
            for _, road in network_df.iterrows():
                from_idx = node_to_idx[road['from_node']]
                to_idx = node_to_idx[road['to_node']]
                edges.append((from_idx, to_idx))
            
            adjacency_data = {
                'edges': np.array(edges),
                'node_ids': np.array(list(node_to_idx.keys())),
                'node_mapping': node_to_idx
            }
        
        # 10. Save road attributes
        network_attributes = {}
        for col in network_df.columns:
            if col != 'geometry' and col != 'wkb':
                network_attributes[col] = network_df[col].values
        
        sensor_attributes = {}
        for col in sensor_roads.columns:
            if col != 'geometry' and col != 'wkb':
                sensor_attributes[col] = sensor_roads[col].values
        
        # 11. Save as npz file
        save_dict = {
            # Time data
            'timestamps': np.array(timestamps),
            
            # Network data (complete)
            'network_road_ids': network_df[road_id_col].values,
            'network_detector_ids': network_df['detid'].values,
            'network_attributes': network_attributes,
            
            # Sensor road data (subset)
            'sensor_road_ids': sensor_roads[road_id_col].values,
            'sensor_detector_ids': sensor_roads['detid'].values,
            'sensor_attributes': sensor_attributes,
            
            # Mapping relationship
            'network_to_sensor_map': network_to_sensor,  # network index -> sensor index
            'sensor_to_network_map': sensor_to_network,  # sensor index -> network index
            
            # Sensor count and network count
            'n_network_roads': len(network_df),
            'n_sensor_roads': len(sensor_roads)
        }
        
        # Add metric data (only for sensor roads)
        for col_name, array in data_arrays.items():
            save_dict[f'sensor_{col_name}'] = array
        
        # Add network connection structure (if any)
        if adjacency_data:
            for key, value in adjacency_data.items():
                save_dict[f'network_{key}'] = value
        
        np.savez_compressed(output_npz, **save_dict)
        
        elapsed_time = time.time() - start_time
        print(f"Successfully converted {city_name} data to NPZ in {elapsed_time:.2f} seconds")
        print(f"Saved to: {output_npz}")
        
        # 12. Print some statistical information
        print("\nData summary:")
        print(f"Complete network roads: {len(network_df)}")
        print(f"Roads with sensors: {len(sensor_roads)} ({len(sensor_roads)/len(network_df)*100:.2f}%)")
        print(f"Number of time points: {n_times}")
        
        for col_name, array in data_arrays.items():
            non_nan = np.count_nonzero(~np.isnan(array))
            coverage = non_nan / (array.shape[0] * array.shape[1]) * 100
            print(f"  {col_name} coverage: {coverage:.2f}% ({non_nan} non-NaN values)")
        
        if adjacency_data:
            print(f"Network nodes: {len(adjacency_data['node_ids'])}")
            print(f"Network edges: {len(adjacency_data['edges'])}")
        
        return True
    
    except Exception as e:
        print(f"Error converting {city_name} data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Root directory
    data_root = r"data\debug\input"
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    
    print(f"Found {len(city_folders)} city folders")
    print("Using optimized structure: complete network + sensor data mapping")
    
    # Create progress file path
    progress_file = os.path.join(data_root, "npz_conversion_progress.txt")
    
    # Load processed cities from progress file (if exists)
    processed_cities = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            processed_cities = set(line.strip() for line in f.readlines())
        print(f"Loaded progress: {len(processed_cities)} cities already processed")
    
    # Record overall progress
    total_cities = len(city_folders)
    successful_count = len(processed_cities)
    
    # Process each city
    for city_folder in city_folders:
        city_name = os.path.basename(city_folder)
        
        # If city has been processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already processed")
            continue
        
        # Convert data
        success = convert_to_optimized_npz(city_folder)
        
        # If processed successfully, record progress
        if success:
            successful_count += 1
            processed_cities.add(city_name)
            
            # Update progress file
            with open(progress_file, 'w') as f:
                for city in processed_cities:
                    f.write(f"{city}\n")
        
        # Display current progress
        print(f"Progress: {successful_count}/{total_cities} cities processed ({successful_count/total_cities*100:.1f}%)\n")
    
    print(f"Conversion complete! {successful_count}/{total_cities} cities successfully processed.")
    
    # Provide a simple example of how to use the converted data
    print("\nUsage example:")
    print("```python")
    print("# Load NPZ file")
    print("data = np.load('city_traffic_network.npz')")
    print("")
    print("# Access complete network data")
    print("network_roads = data['network_road_ids']")
    print("network_detids = data['network_detector_ids']")
    print("")
    print("# Access sensor data")
    print("sensor_flow = data['sensor_flow']  # Matrix of timestamps x sensor roads")
    print("sensor_detids = data['sensor_detector_ids']")
    print("")
    print("# Use mapping relationships")
    print("network_to_sensor = data['network_to_sensor_map'].item()  # Extract dict from npz")
    print("sensor_to_network = data['sensor_to_network_map'].item()")
    print("")
    print("# Example: Find sensor data for a network index")
    print("network_idx = 42  # A road index in the network")
    print("if network_idx in network_to_sensor:")
    print("    sensor_idx = network_to_sensor[network_idx]")
    print("    flow_data = sensor_flow[:, sensor_idx]  # Traffic flow data for all timestamps on this road")
    print("```")

if __name__ == "__main__":
    main() 