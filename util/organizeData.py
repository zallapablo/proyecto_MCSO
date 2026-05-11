import os
import shutil
import glob
from pathlib import Path
import time

def create_directory(directory):
    """Create directory if it does not exist"""
    os.makedirs(directory, exist_ok=True)

def copy_file(source, destination):
    """Copy file, ensuring the destination directory exists"""
    dest_dir = os.path.dirname(destination)
    create_directory(dest_dir)
    
    if os.path.exists(source):
        shutil.copy2(source, destination)
        return True
    else:
        return False

def organize_city_data(city_name, source_root, weather_root, target_root, copy_instead_of_move=True):
    """
    Organize and move data for a single city
    
    Parameters:
    - city_name: Name of the city
    - source_root: Source data root directory (001_Integrated...)
    - weather_root: Weather data root directory (processed/ear5_city)
    - target_root: Target root directory (000_IUTFD)
    - copy_instead_of_move: If True, copy files, if False, move files
    
    Returns:
    - (Number of successfully processed files, Total number of files)
    """
    print(f"\nProcessing {city_name}...")
    
    # Source paths
    source_city_dir = os.path.join(source_root, city_name)
    weather_city_dir = os.path.join(weather_root, city_name, "weather")
    
    # Target paths
    target_city_dir = os.path.join(target_root, city_name)
    target_roads_dir = os.path.join(target_city_dir, "roads")
    target_sensors_dir = os.path.join(target_city_dir, "sensors")
    target_npz_dir = os.path.join(target_city_dir, "npz")
    target_weather_dir = os.path.join(target_city_dir, "weather")
    target_datetime_dir = os.path.join(target_weather_dir, "datetime")
    
    # Create target directories
    create_directory(target_roads_dir)
    create_directory(target_sensors_dir)
    create_directory(target_npz_dir)
    create_directory(target_weather_dir)
    create_directory(target_datetime_dir)
    
    # Define files to transfer
    files_to_process = [
        # (Source file, Target file)
        # Metadata file - placed directly in the city root directory
        (os.path.join(source_city_dir, f"{city_name}_metadata.json"), os.path.join(target_city_dir, f"{city_name}_metadata.json")),
        
        # Road network files
        (os.path.join(source_city_dir, "roads.parquet"), os.path.join(target_roads_dir, "roads.parquet")),
        (os.path.join(source_city_dir, "selected_network.parquet"), os.path.join(target_roads_dir, "selected_network.parquet")),
        
        # Sensor data files
        (os.path.join(source_city_dir, "detectors.parquet"), os.path.join(target_sensors_dir, "detectors_info.parquet")),
        (os.path.join(source_city_dir, "hourly_readings.parquet"), os.path.join(target_sensors_dir, "hourly_readings.parquet")),
        (os.path.join(source_city_dir, "5min_readings.parquet"), os.path.join(target_sensors_dir, "5min_readings.parquet")),
        
        # NPZ files
        (os.path.join(source_city_dir, f"{city_name}_traffic_network.npz"), os.path.join(target_npz_dir, f"{city_name}_traffic_network.npz")),
        
        # Weather data
        (os.path.join(weather_city_dir, "grid_info.parquet"), os.path.join(target_weather_dir, "grid_info.parquet")),
    ]
    
    # Find and add rainfall files
    if os.path.exists(weather_city_dir):
        rainfall_files = glob.glob(os.path.join(weather_city_dir, "local_hourly_rainfall_*.parquet"))
        for rainfall_file in rainfall_files:
            filename = os.path.basename(rainfall_file)
            files_to_process.append((rainfall_file, os.path.join(target_datetime_dir, filename)))
    
    # Process all files
    success_count = 0
    for source_file, dest_file in files_to_process:
        try:
            if not os.path.exists(source_file):
                print(f"  Warning: Source file not found: {source_file}")
                continue
                
            if os.path.exists(dest_file):
                print(f"  Skipping, already exists: {dest_file}")
                success_count += 1
                continue
                
            # Copy or move file
            if copy_instead_of_move:
                shutil.copy2(source_file, dest_file)
                print(f"  Copied: {source_file} -> {dest_file}")
            else:
                shutil.move(source_file, dest_file)
                print(f"  Moved: {source_file} -> {dest_file}")
                
            success_count += 1
            
        except Exception as e:
            print(f"  Error processing {source_file}: {str(e)}")
    
    print(f"Completed {city_name}: {success_count}/{len(files_to_process)} files processed")
    return success_count, len(files_to_process)

def main():
    # Configuration parameters
    SOURCE_ROOT = r"data\debug\input"
    WEATHER_ROOT = r"data\debug\output\city_whole"
    TARGET_ROOT = r"data\debug\IUTFD"
    
    # Whether to copy instead of move files
    COPY_INSTEAD_OF_MOVE = True  # Set to False to move files instead of copy
    
    # Create target root directory
    create_directory(TARGET_ROOT)
    
    # Get city list
    city_dirs = [d for d in glob.glob(os.path.join(SOURCE_ROOT, "*")) if os.path.isdir(d)]
    city_names = [os.path.basename(d) for d in city_dirs]
    
    print(f"Found {len(city_names)} cities")
    print(f"Operation mode: {'Copy' if COPY_INSTEAD_OF_MOVE else 'Move'}")
    
    # Create progress file
    progress_file = os.path.join(TARGET_ROOT, "organization_progress.txt")
    
    # Load processed cities from progress file
    processed_cities = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            processed_cities = set(line.strip() for line in f.readlines())
        print(f"Loaded progress: {len(processed_cities)} cities already processed")
    
    # Record overall progress
    total_cities = len(city_names)
    successful_count = len(processed_cities)
    total_files = 0
    total_success = 0
    
    # Process each city
    start_time = time.time()
    for city_name in city_names:
        # If city is already processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already processed")
            continue
        
        # Organize city data
        success_files, total_files_city = organize_city_data(
            city_name, 
            SOURCE_ROOT, 
            WEATHER_ROOT, 
            TARGET_ROOT,
            COPY_INSTEAD_OF_MOVE
        )
        
        total_files += total_files_city
        total_success += success_files
        
        # If successfully processed, record progress
        if success_files > 0:
            successful_count += 1
            processed_cities.add(city_name)
            
            # Update progress file
            with open(progress_file, 'w') as f:
                for city in processed_cities:
                    f.write(f"{city}\n")
        
        # Show progress
        print(f"Progress: {successful_count}/{total_cities} cities processed ({successful_count/total_cities*100:.1f}%)")
    
    # Show summary
    elapsed_time = time.time() - start_time
    print("\nOrganization complete!")
    print(f"Processed {successful_count}/{total_cities} cities")
    print(f"Processed {total_success}/{total_files} files")
    print(f"Total time: {elapsed_time:.2f} seconds")
    
    # Verify results
    print("\nVerifying new directory structure...")
    verify_structure(TARGET_ROOT)

def verify_structure(target_root):
    """Verify the newly created directory structure"""
    city_dirs = [d for d in glob.glob(os.path.join(target_root, "*")) if os.path.isdir(d)]
    
    for city_dir in city_dirs:
        city_name = os.path.basename(city_dir)
        print(f"\nVerifying {city_name}...")
        
        # Check metadata file
        metadata_file = os.path.join(city_dir, f"{city_name}_metadata.json")
        if os.path.exists(metadata_file):
            print(f"  ✓ metadata.json: file exists")
        else:
            print(f"  ✗ metadata.json: file missing")
        
        # Check if each subdirectory exists
        subdirs = ["roads", "sensors", "npz", "weather", os.path.join("weather", "datetime")]
        for subdir in subdirs:
            full_path = os.path.join(city_dir, subdir)
            if os.path.exists(full_path):
                files = glob.glob(os.path.join(full_path, "*"))
                print(f"  ✓ {subdir}: {len(files)} files")
            else:
                print(f"  ✗ {subdir}: directory missing")

if __name__ == "__main__":
    main() 