import pandas as pd
import numpy as np
import os
import glob
from pathlib import Path
import time

def calculate_hourly_data(sensor_df):
    """
    Aggregate 5-minute interval sensor data into hourly data
    
    Parameters:
    - sensor_df: DataFrame containing sensor data
    
    Returns:
    - hourly_df: Aggregated hourly data
    """
    # Ensure the time column format is correct
    sensor_df['day'] = pd.to_datetime(sensor_df['day'])
    
    # Create a datetime column combining date and interval
    sensor_df['datetime'] = sensor_df['day'] + pd.to_timedelta(sensor_df['interval'], unit='s')
    # Create hourly timestamps
    sensor_df['hour'] = sensor_df['datetime'].dt.floor('h')
    # Group by hour, sensor ID, and city
    grouped = sensor_df.groupby(['hour', 'detid', 'city'])
    
    # Initialize result list
    hourly_data = []
    
    for (hour, detid, city), group in grouped:
        # Calculate number of samples
        samples_count = len(group)
        
        # 1. Flow: sum and mean
        flow_sum = group['flow'].sum()
        flow_mean_5min = flow_sum / samples_count if samples_count > 0 else 0
        
        # 2. Speed: check if column exists and has non-NaN values
        has_speed_column = 'speed' in group.columns
        has_valid_speed = has_speed_column and not group['speed'].isna().all()
        
        # Set default values
        speed_mean = np.nan
        speed_weight = np.nan
        
        # If valid speed data exists, calculate mean
        if has_valid_speed:
            speed_mean = group['speed'].mean()
            
            # Filter out rows where speed is NaN
            valid_data = group.dropna(subset=['speed'])
            
            # Calculate flow-weighted average speed
            if not valid_data.empty and valid_data['flow'].sum() > 0:
                speed_weight = np.average(
                    valid_data['speed'], 
                    weights=valid_data['flow'],
                    axis=0
                )
        
        # 3. Occupancy: arithmetic mean
        occ_mean = group['occ'].mean()
        
        # 4. Statistical error rate
        error_mean = group['error'].mean() if 'error' in group.columns else np.nan
        
        # 5. Format datetime to specific format (DD/MM/YYYY HH:MM:SS)
        formatted_datetime = hour.strftime('%d/%m/%Y %H:%M:%S')
        
        # Add to result list
        hourly_data.append({
            'datetime': formatted_datetime,
            'detid': detid,
            'flow_sum': flow_sum,
            'flow_mean_5min': flow_mean_5min,
            'occ_mean': occ_mean,
            'speed_mean': speed_mean,
            'speed_weight': speed_weight,
            'error_mean': error_mean,
            'city': city
        })
    
    # Convert to DataFrame
    hourly_df = pd.DataFrame(hourly_data)
    
    return hourly_df

def process_city_sensor_data(city_folder):
    """Process sensor data for a city and save hourly aggregated results"""
    
    city_name = os.path.basename(city_folder)
    sensor_file = os.path.join(city_folder, f"{city_name}.csv")
    output_file = os.path.join(city_folder, "hourly_readings.parquet")
    
    # Check if the result file for the city already exists (resume from break point)
    if os.path.exists(output_file):
        print(f"Skipping {city_name} - already processed")
        return True
    
    if not os.path.exists(sensor_file):
        print(f"No sensor data found for {city_name}")
        return False
    
    try:
        start_time = time.time()
        print(f"Processing {city_name} sensor data...")
        
        # Read sensor data
        sensor_df = pd.read_csv(sensor_file)
        
        # Calculate hourly data
        hourly_df = calculate_hourly_data(sensor_df)
        
        # Save results to city folder
        hourly_df.to_parquet(output_file, index=False)
        
        elapsed_time = time.time() - start_time
        print(f"Processed {city_name} in {elapsed_time:.2f} seconds - Saved to {output_file}")
        
        return True
    except Exception as e:
        print(f"Error processing {city_name}: {str(e)}")
        return False

def main():
    # Root directory
    data_root = r"data\debug\input"
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    
    # Create progress file path
    progress_file = os.path.join(data_root, "hourly_processing_progress.txt")
    
    # Load processed cities from progress file (if exists)
    processed_cities = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            processed_cities = set(line.strip() for line in f.readlines())
        print(f"Loaded progress: {len(processed_cities)} cities already processed")
    
    # Record overall progress
    total_cities = len(city_folders)
    successful_count = len(processed_cities)
    
    print(f"Found {total_cities} cities, {total_cities - successful_count} remaining to process")
    
    # Process each city, skip already processed ones
    for city_folder in city_folders:
        city_name = os.path.basename(city_folder)
        
        # If city is already processed, skip
        if city_name in processed_cities:
            print(f"Skipping {city_name} - already in progress file")
            continue
        
        # Process city data
        success = process_city_sensor_data(city_folder)
        
        # If processed successfully, record progress
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
    
    # Count how many cities successfully generated hourly_readings.parquet file
    actual_files = len([f for f in city_folders if os.path.exists(os.path.join(f, "hourly_readings.parquet"))])
    print(f"Verified {actual_files} hourly_readings.parquet files in city folders")

if __name__ == "__main__":
    main() 