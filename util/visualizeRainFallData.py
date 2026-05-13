import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import os
from datetime import timedelta

def get_continuous_periods(dates):
    """Identify continuous time periods"""
    dates = sorted(dates)
    periods = []
    current_period = [dates[0]]
    
    for i in range(1, len(dates)):
        current_date = pd.to_datetime(dates[i])
        previous_date = pd.to_datetime(dates[i-1])
        
        if (current_date - previous_date).days == 1:
            current_period.append(dates[i])
        else:
            periods.append(current_period)
            current_period = [dates[i]]
    
    periods.append(current_period)
    return periods

def plot_city_rainfall(city_name, data_dir="data/processed/ear5_city"):
    """Create rainfall time series plot for a specified city"""
    # Set plot style
    plt.style.use('seaborn-v0_8')  # Use matplotlib built-in seaborn style
    sns.set_palette("husl")
    
    # Read all rainfall data for the city
    weather_dir = Path(data_dir) / city_name / 'weather'
    if not weather_dir.exists():
        print(f"Cannot find data directory for city {city_name}")
        return
    
    # Read grid info
    grid_info = pd.read_parquet(weather_dir / 'grid_info.parquet')
    grid_count = len(grid_info)
    
    # Collect all data files
    data_files = list(weather_dir.glob('local_hourly_rainfall_*.parquet'))
    if not data_files:
        print(f"No rainfall data found for city {city_name}")
        return
    
    # Get all dates
    dates = [pd.to_datetime(f.stem.split('_')[-1]).strftime('%Y-%m-%d') 
            for f in data_files if f.stem.startswith('local_hourly_rainfall_')]
    
    # Identify continuous time periods
    periods = get_continuous_periods(dates)
    
    # Create output directory
    output_dir = Path(data_dir) / city_name / 'plots'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create charts for each continuous time period
    for period in periods:
        # Collect data for this period
        period_data = []
        for date in period:
            df = pd.read_parquet(weather_dir / f'local_hourly_rainfall_{date}.parquet')
            period_data.append(df)
        
        if not period_data:
            continue
            
        # Merge data
        combined_df = pd.concat(period_data)
        combined_df['datetime'] = pd.to_datetime(combined_df['local_time'])
        
        # Create plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), height_ratios=[2, 1])
        
        # Create period name
        if len(period) == 1:
            period_name = period[0]
        else:
            period_name = f"{period[0]}_to_{period[-1]}"
            
        fig.suptitle(f'{city_name.capitalize()} Rainfall Analysis\n{period_name}', fontsize=16)
        
        # Calculate statistics for each time point
        hourly_stats = combined_df.groupby('datetime').agg({
            'total_precipitation': ['mean', 'std', 'min', 'max'],
            'large_scale_rain_rate': ['mean', 'std', 'min', 'max']
        })
        
        # Plot total precipitation
        ax1.fill_between(hourly_stats.index, 
                         hourly_stats[('total_precipitation', 'mean')] - hourly_stats[('total_precipitation', 'std')],
                         hourly_stats[('total_precipitation', 'mean')] + hourly_stats[('total_precipitation', 'std')],
                         alpha=0.3)
        ax1.plot(hourly_stats.index, hourly_stats[('total_precipitation', 'mean')], 
                 label='Total Precipitation (mean)', linewidth=2)
        ax1.set_ylabel('Total Precipitation (mm)')
        ax1.legend()
        
        # Plot large scale rain rate
        ax2.fill_between(hourly_stats.index,
                         hourly_stats[('large_scale_rain_rate', 'mean')] - hourly_stats[('large_scale_rain_rate', 'std')],
                         hourly_stats[('large_scale_rain_rate', 'mean')] + hourly_stats[('large_scale_rain_rate', 'std')],
                         alpha=0.3)
        ax2.plot(hourly_stats.index, hourly_stats[('large_scale_rain_rate', 'mean')], 
                 label='Large Scale Rain Rate (mean)', linewidth=2, color='green')
        ax2.set_ylabel('Large Scale Rain Rate (mm/h)')
        ax2.legend()
        
        # Format x axis
        for ax in [ax1, ax2]:
            ax.grid(True)
            ax.set_xlabel('Time')
            plt.setp(ax.get_xticklabels(), rotation=45)
        
        # Add grid info
        plt.figtext(0.02, 0.02, f'Number of ERA5 grids: {grid_count}', fontsize=8)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save plot
        plt.savefig(output_dir / f'{city_name}_rainfall_{period_name}.png', dpi=300, bbox_inches='tight')
        plt.close()

def main():
    data_dir = "data/processed/ear5_city"
    
    # Get all cities
    cities = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    print(f"Found {len(cities)} cities")
    for city in cities:
        print(f"\nProcessing city: {city}")
        try:
            plot_city_rainfall(city, data_dir)
            print(f"Successfully created rainfall analysis plot for {city}")
        except Exception as e:
            print(f"Error processing city {city}: {str(e)}")

if __name__ == "__main__":
    main() 