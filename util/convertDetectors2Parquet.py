import os
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import time
from pathlib import Path

def convert_detector_csv_to_parquet(city_folder):
    """
    Convert detectors_public.csv in the city folder to parquet format,
    and convert longitude and latitude to point geometry data
    
    Parameters:
    - city_folder: path to city data folder
    
    Returns:
    - bool: whether the conversion was successful
    """
    city_name = os.path.basename(city_folder)
    print(f"Processing {city_name} detector data...")
    
    # Define file paths
    csv_file = os.path.join(city_folder, "detectors_public.csv")
    parquet_file = os.path.join(city_folder, "detectors.parquet")
    
    # Check if file already exists (resume breakpoint)
    if os.path.exists(parquet_file):
        print(f"Skipping {city_name} - detector parquet already exists")
        return True
    
    # Check if source file exists
    if not os.path.exists(csv_file):
        print(f"Warning: detectors_public.csv not found for {city_name}")
        return False
    
    try:
        start_time = time.time()
        
        # Read CSV file
        detector_df = pd.read_csv(csv_file)
        
        # Ensure long and lat columns exist
        if 'long' not in detector_df.columns or 'lat' not in detector_df.columns:
            print(f"  Warning: long or lat columns missing in {city_name}, skipping geometry creation")
            detector_df.to_parquet(parquet_file, index=False)
        else:
            # Create point geometry objects
            print(f"  Creating point geometry from long/lat coordinates")
            geometry = [Point(x, y) for x, y in zip(detector_df['long'], detector_df['lat'])]
            
            # Convert to GeoDataFrame
            geo_detector_df = gpd.GeoDataFrame(
                detector_df, 
                geometry=geometry, 
                crs="EPSG:4326"  # WGS84 coordinate system
            )
            
            # Print some basic information
            print(f"  Successfully created geometry for {len(geo_detector_df)} detectors in {city_name}")
            
            # Save as Parquet format
            geo_detector_df.to_parquet(parquet_file, index=False)
        
        # Calculate file size reduction
        csv_size = os.path.getsize(csv_file) / 1024  # KB
        parquet_size = os.path.getsize(parquet_file) / 1024  # KB
        reduction = (1 - parquet_size / csv_size) * 100 if csv_size > 0 else 0
        
        elapsed_time = time.time() - start_time
        print(f"  Converted in {elapsed_time:.2f} seconds")
        print(f"  File size: CSV={csv_size:.2f}KB, Parquet={parquet_size:.2f}KB ({reduction:.1f}% reduction)")
        
        return True
    
    except Exception as e:
        print(f"Error converting {city_name} detectors: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Process detector data conversion for all cities"""
    
    # Root directory
    data_root = "data\debug\input"
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    print(f"Found {len(city_folders)} city folders")
    
    # Create progress file path
    progress_file = os.path.join(data_root, "detector_conversion_progress.txt")
    
    # Load processed cities from progress file (if it exists)
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
        
        # If the city has already been processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already in progress file")
            continue
        
        # Process city data
        success = convert_detector_csv_to_parquet(city_folder)
        
        # If processed successfully, record progress
        if success:
            successful_count += 1
            processed_cities.add(city_name)
            
            # Update progress file
            with open(progress_file, 'w') as f:
                for city in processed_cities:
                    f.write(f"{city}\n")
        
        # Display current progress
        print(f"Progress: {successful_count}/{total_cities} cities processed ({successful_count/total_cities*100:.1f}%)")
    
    print(f"Conversion complete! {successful_count}/{total_cities} cities successfully processed.")
    
    # Calculate overall file size change
    total_csv_size = 0
    total_parquet_size = 0
    
    for city_folder in city_folders:
        csv_file = os.path.join(city_folder, "detectors_public.csv")
        parquet_file = os.path.join(city_folder, "detectors_info.parquet")
        
        if os.path.exists(csv_file):
            total_csv_size += os.path.getsize(csv_file)
        
        if os.path.exists(parquet_file):
            total_parquet_size += os.path.getsize(parquet_file)
    
    if total_csv_size > 0:
        total_reduction = (1 - total_parquet_size / total_csv_size) * 100
        print(f"\nTotal file size:")
        print(f"  CSV: {total_csv_size/1024:.2f}KB")
        print(f"  Parquet: {total_parquet_size/1024:.2f}KB")
        print(f"  Reduction: {total_reduction:.1f}%")
    
    # Provide usage example
    print("\nHow to use the converted data:")
    print("```python")
    print("import geopandas as gpd")
    print("")
    print("# Read Parquet file with geometric data")
    print("detectors = gpd.read_parquet('data/debug/input/augsburg/detectors_info.parquet')")
    print("")
    print("# Access point geometry data")
    print("for idx, detector in detectors.iterrows():")
    print("    print(f\"Detector {detector['detid']} at {detector.geometry}\")")
    print("")
    print("# Plot sensor locations")
    print("import matplotlib.pyplot as plt")
    print("detectors.plot()")
    print("plt.title('Detector Locations')")
    print("plt.show()")
    print("```")

if __name__ == "__main__":
    main() 