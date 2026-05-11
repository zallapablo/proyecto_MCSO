import cdsapi
import pandas as pd
import xarray as xr
import os
from pathlib import Path
import json

def load_download_progress(progress_file):
    """Load download progress"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {'downloaded_dates': []}

def save_download_progress(progress_file, downloaded_dates):
    """Save download progress"""
    with open(progress_file, 'w') as f:
        json.dump({'downloaded_dates': downloaded_dates}, f)

def download_era5_rainfall(date, output_dir):
    """
    Download ERA5 rainfall data
    date: Date (Format: YYYY-MM-DD)
    output_dir: Output directory
    """
    output_file = f"{output_dir}/era5_rainfall_{date}.grib"
    if os.path.exists(output_file):
        print(f"Skipping already downloaded date: {date}")
        return output_file
    
    client = cdsapi.Client()
    request = {
        "product_type": "reanalysis",
        "variable": [
            "total_precipitation",
            "large_scale_rain_rate",
            "precipitation_type"
        ],
        "year": [date[:4]],
        "month": [date[5:7]],
        "day": [date[8:]],
        "time": [
            "00:00", "01:00", "02:00",
            "03:00", "04:00", "05:00",
            "06:00", "07:00", "08:00",
            "09:00", "10:00", "11:00",
            "12:00", "13:00", "14:00",
            "15:00", "16:00", "17:00",
            "18:00", "19:00", "20:00",
            "21:00", "22:00", "23:00"
        ],
        "data_format": "grib",
        "download_format": "unarchived"
    }
    
    print(f"Starting to download data for {date}...")
    # Download data
    client.retrieve(
        "reanalysis-era5-single-levels",
        request,
        output_file
    )
    print(f"Finished downloading data for {date}")
    return output_file

def process_era5_data(): 
    # Read the previously generated date file
    dates_df = pd.read_csv(r'data\debug\output\all_unique_dates.csv')
    
    # Create output directory
    output_dir = r"G:\002_Data\007_ERA5\000_weather"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Progress file path
    progress_file = os.path.join(output_dir, 'download_progress.json')
    
    # Load previously downloaded progress
    progress = load_download_progress(progress_file)
    downloaded_dates = set(progress['downloaded_dates'])
    
    # Get all dates that need to be downloaded
    all_dates = pd.to_datetime(dates_df['date'])
    all_dates = all_dates.sort_values()
    
    total_dates = len(all_dates)
    processed_count = 0
    
    try:
        for date in all_dates:
            date_str = date.strftime('%Y-%m-%d')
            processed_count += 1
            
            # Skip if the date is already downloaded
            if date_str in downloaded_dates:
                print(f"Skipping already downloaded date: {date_str} ({processed_count}/{total_dates})")
                continue
            
            try:
                print(f"Processing date: {date_str} ({processed_count}/{total_dates})")
                # Download single day data
                grib_file = download_era5_rainfall(date_str, output_dir)
                
                # Mark as downloaded
                downloaded_dates.add(date_str)
                save_download_progress(progress_file, list(downloaded_dates))
                
            except Exception as e:
                print(f"Error occurred while downloading data for {date_str}: {str(e)}")
                # Save progress and continue to the next date
                save_download_progress(progress_file, list(downloaded_dates))
                continue
        
        print("All ERA5 data download completed!")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print("Saved download progress, will resume from interruption next time")
        # Ensure progress is saved even if an error occurs
        save_download_progress(progress_file, list(downloaded_dates))

if __name__ == "__main__":
    process_era5_data() 