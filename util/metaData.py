import os
import json
import pandas as pd
import geopandas as gpd
import glob
from pathlib import Path
import numpy as np
from datetime import datetime

def generate_city_metadata(city_folder):
    """Generate metadata JSON file for a specified city"""
    
    city_name = os.path.basename(city_folder)
    print(f"Generating metadata for {city_name}...")
    
    # Define input file paths
    network_geojson_path = os.path.join(city_folder, "selected_network_4326.geojson")
    rainfall_csv_path = os.path.join(city_folder, "rainfall_data.csv")
    detectors_csv_path = os.path.join(city_folder, "detectors_public.csv")
    readings_parquet_path = os.path.join(city_folder, "5min_readings.parquet")
    
    # Check if necessary files exist
    if not os.path.exists(network_geojson_path):
        print(f"Error: selected_network_4326.geojson not found for {city_name}")
        return None
    
    if not os.path.exists(rainfall_csv_path):
        print(f"Error: rainfall_data.csv not found for {city_name}")
        return None
    
    metadata = {
        "city": city_name,
        "time_range": {
            "start": "",
            "end": "",
            "resolutions": {
                "weather": "1h",
                "traffic": "5min"
            }
        },
        "spatial_bounds": {
            "bbox": [],
            "projection": "EPSG:4326"
        },
        "data_summary": {
            "num_roads": 0,
            "num_sensors": 0,
            "num_timepoints": 0
        },
        "relationships": {
            "road_to_detector": "one_to_one",
            "road_to_weather": "one_to_many"
        }
    }
    
    # Get spatial bounds and road count from network geojson
    try:
        network_gdf = gpd.read_file(network_geojson_path)
        bounds = network_gdf.total_bounds  # [minx, miny, maxx, maxy]
        metadata["spatial_bounds"]["bbox"] = bounds.tolist()
        metadata["data_summary"]["num_roads"] = len(network_gdf)
        print(f"Extracted spatial bounds and road count from network geojson")
    except Exception as e:
        print(f"Error processing network geojson: {str(e)}")
        return None
    
    # Get time range from rainfall_data.csv
    try:
        rainfall_df = pd.read_csv(rainfall_csv_path)
        if 'date' in rainfall_df.columns:
            # Ensure consistent date format
            rainfall_df['date'] = pd.to_datetime(rainfall_df['date'])
            start_date = rainfall_df['date'].min().strftime('%Y-%m-%d')
            end_date = rainfall_df['date'].max().strftime('%Y-%m-%d')
            metadata["time_range"]["start"] = start_date
            metadata["time_range"]["end"] = end_date
            print(f"Extracted time range from rainfall data: {start_date} to {end_date}")
        else:
            print("Warning: 'date' column not found in rainfall data")
    except Exception as e:
        print(f"Error processing rainfall data: {str(e)}")
        return None
    
    # Get sensor count from detectors_public.csv
    if os.path.exists(detectors_csv_path):
        try:
            detectors_df = pd.read_csv(detectors_csv_path)
            metadata["data_summary"]["num_sensors"] = len(detectors_df)
            print(f"Extracted sensor count: {len(detectors_df)}")
        except Exception as e:
            print(f"Error processing detectors data: {str(e)}")
    else:
        print(f"Warning: detectors_public.csv not found for {city_name}")
    
    # Get timepoint count from 5min_readings.parquet
    if os.path.exists(readings_parquet_path):
        try:
            # Try reading the entire file directly without nrows param
            readings_df = pd.read_parquet(readings_parquet_path)
            
            # Try to find time column (might be 'datetime' or other names)
            time_column = None
            for potential_col in ['datetime', 'timestamp', 'time', 'date']:
                if potential_col in readings_df.columns:
                    time_column = potential_col
                    break
            
            if time_column:
                num_timepoints = readings_df[time_column].nunique()
                metadata["data_summary"]["num_timepoints"] = int(num_timepoints)
                print(f"Extracted timepoint count: {num_timepoints}")
            else:
                print("Warning: No time column found in readings data")
        except Exception as e:
            print(f"Error processing readings data: {str(e)}")
    else:
        print(f"Warning: 5min_readings.parquet not found for {city_name}")
    
    # Save metadata to JSON file
    metadata_path = os.path.join(city_folder, f"{city_name}_metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Saved metadata to {metadata_path}")
    return metadata

def main():
    # Root directory
    data_root = r"data\debug\input"
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    
    print(f"Found {len(city_folders)} city folders")
    
    # Process each city
    for city_folder in city_folders:
        generate_city_metadata(city_folder)
    
    print("Metadata generation complete!")

if __name__ == "__main__":
    main() 