import pandas as pd
import os
import glob
from pathlib import Path
import time

def convert_csv_to_parquet(csv_file, output_file):
    """
    Convert sensor CSV file to Parquet format
    
    Parameters:
    - csv_file: CSV file path
    - output_file: output Parquet file path
    
    Returns:
    - bool: whether the conversion was successful
    """
    try:
        # Read CSV file
        df = pd.read_csv(csv_file)
        
        # Ensure required columns exist
        required_cols = ['day', 'interval', 'detid', 'flow', 'occ', 'city']
        for col in required_cols:
            if col not in df.columns:
                print(f"Error: Required column '{col}' not found in {csv_file}")
                return False
        
        # Add missing columns (if needed)
        if 'error' not in df.columns:
            df['error'] = None
        if 'speed' not in df.columns:
            df['speed'] = None
        
        # Convert datetime
        df['day'] = pd.to_datetime(df['day'])
        df['datetime'] = df['day'] + pd.to_timedelta(df['interval'], unit='s')
        
        # Format datetime as DD/MM/YYYY HH:MM:SS
        df['datetime'] = df['datetime'].dt.strftime('%d/%m/%Y %H:%M:%S')
        
        # Select and rename columns
        result_df = df[['datetime', 'detid', 'flow', 'occ', 'speed', 'error', 'city']]
        
        # Save as Parquet file
        result_df.to_parquet(output_file, index=False)
        
        return True
    
    except Exception as e:
        print(f"Error converting {csv_file}: {str(e)}")
        return False

def process_city_folders(data_root):
    """Process all city folders, convert CSV to Parquet"""
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    
    print(f"Found {len(city_folders)} city folders")
    
    # Create progress file path
    progress_file = os.path.join(data_root, "csv2parquet_progress.txt")
    
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
        
        # If city has already been processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already processed")
            continue
        
        # Build file path
        csv_file = os.path.join(city_folder, f"{city_name}.csv")
        parquet_file = os.path.join(city_folder, f"5min_readings.parquet")
        
        if not os.path.exists(csv_file):
            print(f"No sensor CSV file found for {city_name}")
            continue
        
        print(f"Processing {city_name}...")
        start_time = time.time()
        
        # Convert file
        success = convert_csv_to_parquet(csv_file, parquet_file)
        
        if success:
            elapsed_time = time.time() - start_time
            print(f"Converted {city_name} in {elapsed_time:.2f} seconds")
            
            # Update progress
            successful_count += 1
            processed_cities.add(city_name)
            
            # Save progress
            with open(progress_file, 'w') as f:
                for city in processed_cities:
                    f.write(f"{city}\n")
        else:
            print(f"Failed to convert {city_name}")
        
        # Display progress
        print(f"Progress: {successful_count}/{total_cities} cities ({successful_count/total_cities*100:.1f}%)")
    
    print(f"Conversion complete. {successful_count}/{total_cities} cities successfully processed.")
    
    # Verify files
    actual_files = len([f for f in city_folders if os.path.exists(os.path.join(f, "sensor_readings.parquet"))])
    print(f"Verified {actual_files} parquet files in city folders")

def main():
    # Root directory
    data_root = "data\debug\input"
    
    # Process all city folders
    process_city_folders(data_root)

if __name__ == "__main__":
    main() 