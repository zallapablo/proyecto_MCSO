import pandas as pd
import geopandas as gpd
import os
import glob
from pathlib import Path
from shapely.geometry import Point
import numpy as np
import time
import warnings
warnings.filterwarnings("ignore")

def find_nearest_grid(point, grid_gdf):
    """Find the nearest grid cell to a point"""
    # Calculate distance from point to all grid centers
    distances = grid_gdf.geometry.distance(point)
    # Return the grid ID with minimum distance
    return grid_gdf.iloc[distances.argmin()]['grid_id']

def find_containing_grid(point, grid_gdf):
    """Find the grid cell containing a point"""
    # Find all grids containing the point
    containing = grid_gdf[grid_gdf.contains(point)]
    if len(containing) > 0:
        # If there are grids containing the point, return the first one
        return containing.iloc[0]['grid_id']
    else:
        # If no grid contains the point, find the nearest one
        return find_nearest_grid(point, grid_gdf)

def process_road_data(city_folder, grid_data_path):
    """Process road data for a single city, link to grid, and save as Parquet format"""
    city_name = os.path.basename(city_folder)
    print(f"Processing {city_name} road data...")
    
    # Path definitions
    roads_gpkg_path = os.path.join(city_folder, "selected_roads.gpkg")
    network_geojson_path = os.path.join(city_folder, "selected_network_4326.geojson")
    grid_parquet_path = os.path.join(grid_data_path, city_name, "weather", "grid_info.parquet")
    
    # Output Parquet file paths
    roads_parquet_path = os.path.join(city_folder, "roads.parquet")
    network_parquet_path = os.path.join(city_folder, "selected_network.parquet")
    
    # Check if files exist
    files_exist = True
    if not os.path.exists(roads_gpkg_path):
        print(f"Warning: roads.gpkg not found for {city_name}")
        files_exist = False
    
    if not os.path.exists(network_geojson_path):
        print(f"Warning: selected_network_4326.geojson not found for {city_name}")
        files_exist = False
    
    if not os.path.exists(grid_parquet_path):
        print(f"Warning: grid_parquet not found for {city_name}")
        files_exist = False
    
    if not files_exist:
        return False
    
    try:
        start_time = time.time()
        
        # Read grid data
        print(f"Loading grid data for {city_name}...")
        grid_df = pd.read_parquet(grid_parquet_path)
        
        # Convert grid data to GeoDataFrame
        grid_gdf = gpd.GeoDataFrame(
            grid_df, 
            geometry=[Point(xy) for xy in zip(grid_df['longitude'], grid_df['latitude'])],
            crs="EPSG:4326"  # Assuming coordinates are WGS84
        )
        
        # Process roads.gpkg
        if os.path.exists(roads_gpkg_path):
            print(f"Processing roads.gpkg for {city_name}...")
            # roads_gdf = gpd.read_file(roads_gpkg_path, layer="edges")
            roads_gdf = gpd.read_file(roads_gpkg_path)
            
            # Ensure the coordinate systems match
            if roads_gdf.crs != grid_gdf.crs:
                roads_gdf = roads_gdf.to_crs(grid_gdf.crs)
            
            # Method 1: Use spatial join to find the grid for each road segment's centroid
            roads_gdf['centroid'] = roads_gdf.geometry.centroid
            roads_gdf['grid_id'] = roads_gdf['centroid'].apply(lambda point: find_containing_grid(point, grid_gdf))
            
            # Drop the temporary centroid column
            roads_gdf = roads_gdf.drop(columns=['centroid'])
            
            # Update original file (maintain compatibility)
            # roads_gdf.to_file(roads_gpkg_path, driver="GPKG")
            
            # Save as Parquet format (save space)
            roads_gdf.to_parquet(roads_parquet_path, index=False)
            print(f"Saved road data with grid_id to {roads_parquet_path}")
            
            # Calculate space saved
            gpkg_size = os.path.getsize(roads_gpkg_path) / (1024*1024)  # MB
            parquet_size = os.path.getsize(roads_parquet_path) / (1024*1024)  # MB
            space_saved = gpkg_size - parquet_size
            print(f"Space saved: {space_saved:.2f} MB ({(space_saved/gpkg_size)*100:.1f}% reduction)")
        
        # Process selected_network_4326.geojson
        if os.path.exists(network_geojson_path):
            print(f"Processing selected_network_4326.geojson for {city_name}...")
            network_gdf = gpd.read_file(network_geojson_path)
            
            # Ensure the coordinate systems match
            if network_gdf.crs != grid_gdf.crs:
                network_gdf = network_gdf.to_crs(grid_gdf.crs)
            
            # Use spatial join to find the grid for each network feature's centroid
            network_gdf['centroid'] = network_gdf.geometry.centroid
            network_gdf['grid_id'] = network_gdf['centroid'].apply(lambda point: find_containing_grid(point, grid_gdf))
            
            # Drop the temporary centroid column
            network_gdf = network_gdf.drop(columns=['centroid'])
            
            # Update original file (maintain compatibility)
            # network_gdf.to_file(network_geojson_path, driver="GeoJSON")
            
            # Save as Parquet format (save space)
            network_gdf.to_parquet(network_parquet_path, index=False)
            print(f"Saved network data with grid_id to {network_parquet_path}")
            
            # Calculate space saved
            geojson_size = os.path.getsize(network_geojson_path) / (1024*1024)  # MB
            parquet_size = os.path.getsize(network_parquet_path) / (1024*1024)  # MB
            space_saved = geojson_size - parquet_size
            print(f"Space saved: {space_saved:.2f} MB ({(space_saved/geojson_size)*100:.1f}% reduction)")
        
        elapsed_time = time.time() - start_time
        print(f"Processed {city_name} in {elapsed_time:.2f} seconds")
        
        return True
    
    except Exception as e:
        print(f"Error processing {city_name}: {str(e)}")
        return False

def main():
    # Root directories
    data_root = r"data\debug\input"
    grid_data_path = r"data\debug\output\city_whole"
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    
    print(f"Found {len(city_folders)} city folders")
    
    # Create progress file path
    progress_file = os.path.join(data_root, "road2grid_progress.txt")
    
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
        
        # If city is already processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already processed")
            continue
        
        # Process city data
        success = process_road_data(city_folder, grid_data_path)
        
        # If processing successful, record progress
        if success:
            successful_count += 1
            processed_cities.add(city_name)
            
            # Update progress file
            with open(progress_file, 'w') as f:
                for city in processed_cities:
                    f.write(f"{city}\n")
        
        # Show current progress
        print(f"Progress: {successful_count}/{total_cities} cities processed ({successful_count/total_cities*100:.1f}%)")
    
    print(f"Processing complete! {successful_count}/{total_cities} cities successfully processed.")
    
    # Summarize space savings
    total_original_size = 0
    total_parquet_size = 0
    for city_folder in city_folders:
        roads_gpkg = os.path.join(city_folder, "roads.gpkg")
        roads_parquet = os.path.join(city_folder, "roads.parquet")
        network_geojson = os.path.join(city_folder, "selected_network_4326.geojson")
        network_parquet = os.path.join(city_folder, "selected_network.parquet")
        
        if os.path.exists(roads_gpkg) and os.path.exists(roads_parquet):
            total_original_size += os.path.getsize(roads_gpkg)
            total_parquet_size += os.path.getsize(roads_parquet)
        
        if os.path.exists(network_geojson) and os.path.exists(network_parquet):
            total_original_size += os.path.getsize(network_geojson)
            total_parquet_size += os.path.getsize(network_parquet)
    
    # Convert to MB for display
    total_original_mb = total_original_size / (1024*1024)
    total_parquet_mb = total_parquet_size / (1024*1024)
    total_saved_mb = total_original_mb - total_parquet_mb
    
    print(f"\nTotal space usage:")
    print(f"Original formats (GPKG/GeoJSON): {total_original_mb:.2f} MB")
    print(f"Parquet format: {total_parquet_mb:.2f} MB")
    print(f"Total space saved: {total_saved_mb:.2f} MB ({(total_saved_mb/total_original_mb)*100:.1f}% reduction)")

if __name__ == "__main__":
    main()
