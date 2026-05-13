import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
from pathlib import Path
import os
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

def get_processed_files(progress_file):
    """Get all processed time points"""
    processed = set()
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            for line in f:
                # Format: date,time_str
                date_str, time_str = line.strip().split(',')
                processed.add((date_str, time_str))
    return processed

def plot_grib_spatial(grib_file, output_dir, progress_file, processed_times):
    """Create spatial distribution plot for GRIB file"""
    # Read GRIB file
    print(f"Reading file: {grib_file}")
    
    # Get target date from filename
    file_path = Path(grib_file)
    target_date = pd.to_datetime(file_path.stem.split('_')[-1]).date()
    date_str = target_date.strftime('%Y-%m-%d')
    print(f"Target date: {target_date}")
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Processed time points total: {len(processed_times)}")
    
    try:
        # Read precipitation data (edition 1)
        ds_rain = xr.open_dataset(grib_file, engine='cfgrib', 
                                 backend_kwargs={'filter_by_keys': {'edition': 1}})
        
        total_processed = 0
        for time in ds_rain.time:
            time_slice = ds_rain.sel(time=time)
            base_time = pd.Timestamp(time.values) + pd.Timedelta(hours=1)
            
            # Process 12 hours forecast data
            tp_values = time_slice.tp.values
            lsrr_values = time_slice.lsrr.values
            
            valid_hours = len(tp_values)
            for hour in range(valid_hours):
                current_time = base_time + pd.Timedelta(hours=hour)
                
                # Only process target date data
                if current_time.date() == target_date:
                    time_str = current_time.strftime('%Y%m%d_%H%M')
                    
                    # Check if processed
                    if (date_str, time_str) in processed_times:
                        print(f"Skipping processed time point: {time_str}")
                        continue
                    
                    print(f"Processing time point: {current_time}")
                    
                    # Create plot - change to 1 row 3 columns layout
                    fig = plt.figure(figsize=(24, 8))  # Adjust chart size for horizontal layout
                    
                    # 1. Total precipitation (tp)
                    ax1 = plt.subplot(1, 3, 1, projection=ccrs.PlateCarree())
                    lon, lat = np.meshgrid(time_slice.longitude, time_slice.latitude)
                    im1 = ax1.pcolormesh(lon, lat, tp_values[hour],
                                       transform=ccrs.PlateCarree(),
                                       cmap='Blues')
                    ax1.coastlines()
                    ax1.add_feature(cfeature.BORDERS, linestyle=':')
                    plt.colorbar(im1, ax=ax1, label='Total Precipitation (mm)')
                    ax1.set_title(f'Total Precipitation at {current_time}')
                    
                    # 2. Large scale rain rate (lsrr)
                    ax2 = plt.subplot(1, 3, 2, projection=ccrs.PlateCarree())
                    im2 = ax2.pcolormesh(lon, lat, lsrr_values[hour],
                                       transform=ccrs.PlateCarree(),
                                       cmap='Greens')
                    ax2.coastlines()
                    ax2.add_feature(cfeature.BORDERS, linestyle=':')
                    plt.colorbar(im2, ax=ax2, label='Large Scale Rain Rate (mm/h)')
                    ax2.set_title(f'Large Scale Rain Rate at {current_time}')
                    
                    # 3. Precipitation type (if available)
                    try:
                        ds_type = xr.open_dataset(grib_file, engine='cfgrib',
                                                backend_kwargs={'filter_by_keys': {'edition': 2}})
                        type_slice = ds_type.sel(time=time)
                        ptype_values = type_slice.ptype.values[hour]
                        
                        ax3 = plt.subplot(1, 3, 3, projection=ccrs.PlateCarree())
                        im3 = ax3.pcolormesh(lon, lat, ptype_values,
                                           transform=ccrs.PlateCarree(),
                                           cmap='Set3')
                        ax3.coastlines()
                        ax3.add_feature(cfeature.BORDERS, linestyle=':')
                        plt.colorbar(im3, ax=ax3, label='Precipitation Type')
                        ax3.set_title(f'Precipitation Type at {current_time}')
                        ds_type.close()
                    except Exception as e:
                        print(f"Could not read precipitation type data: {str(e)}")
                    
                    # Add overall title
                    plt.suptitle(f'ERA5 Rainfall Data Analysis\n{current_time}', fontsize=16)
                    
                    # Adjust layout
                    plt.tight_layout()
                    
                    # Save image
                    plt.savefig(output_dir / f'spatial_analysis_{time_str}.png',
                               dpi=300, bbox_inches='tight')
                    plt.close()
                    
                    # Save progress
                    total_processed += 1
                    processed_times.add((date_str, time_str))
                    
                    # Update progress file
                    with open(progress_file, 'a') as f:
                        f.write(f"{date_str},{time_str}\n")
                    
                    if total_processed % 10 == 0:  # Output progress every 10 images
                        print(f"Processed {total_processed} new images")
    
    finally:
        # Ensure dataset is closed
        ds_rain.close()
        print(f"Finished processing, generated {total_processed} new images")

def main():
    # Set data directory
    era5_root = Path("G:/002_Data/007_ERA5")
    output_root = Path("data/processed/era5_spatial")
    progress_file = output_root / 'progress.txt'
    
    # Create output root directory
    output_root.mkdir(parents=True, exist_ok=True)
    
    # Get processed time points
    processed_times = get_processed_files(progress_file)
    print(f"Read {len(processed_times)} processed time points from progress file")
    
    # Get all GRIB files
    grib_files = list(era5_root.glob('era5_rainfall_*.grib'))
    
    print(f"Found {len(grib_files)} GRIB files")
    for grib_file in grib_files:
        print(f"\nProcessing file: {grib_file}")
        try:
            date_str = grib_file.stem.split('_')[-1]
            output_dir = output_root / date_str
            plot_grib_spatial(grib_file, output_dir, progress_file, processed_times)
            print(f"Successfully created spatial analysis plots for {date_str}")
        except Exception as e:
            print(f"Error processing file {grib_file}: {str(e)}")
            # Record error message
            with open(output_root / 'errors.log', 'a') as f:
                f.write(f"{grib_file}: {str(e)}\n")
            continue

if __name__ == "__main__":
    main() 