import os
import pandas as pd
from pathlib import Path

def get_all_unique_dates():
    # Set the dataset root directory
    root_dir = r"data\debug\input"
    # Use a dictionary to store dates and corresponding cities
    date_sources = {}

    # Iterate through all city folders in the root directory
    for city_dir in os.listdir(root_dir):
        city_path = os.path.join(root_dir, city_dir)
        print(f"processing: {city_dir}")
        # Ensure it is a directory and not a file
        if os.path.isdir(city_path):
            rainfall_file = os.path.join(city_path, "rainfall_data.csv")
            
            # Check if rainfall_data.csv exists
            if os.path.exists(rainfall_file):
                # Read the CSV file
                df = pd.read_csv(rainfall_file)
                # Get all dates for this city
                for date in df['date'].unique():
                    if date in date_sources:
                        date_sources[date].add(city_dir)
                    else:
                        date_sources[date] = {city_dir}

    # Create a list containing dates and data sources
    data_list = []
    for date in sorted(date_sources.keys()):
        data_list.append({
            'date': date,
            'datasource': ';'.join(sorted(date_sources[date]))
        })
    
    # Create DataFrame
    dates_df = pd.DataFrame(data_list)
    
    # Ensure the output directory exists
    output_dir = "data/processed"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save to CSV file
    output_file = os.path.join(output_dir, "all_unique_dates.csv")
    dates_df.to_csv(output_file, index=False)
    print(f"Saved all unique dates to: {output_file}")
    print(f"Found a total of {len(data_list)} unique dates")

if __name__ == "__main__":
    get_all_unique_dates()
