import os
import sys
import pandas as pd
import geopandas as gpd
import xarray as xr
import numpy as np
from pathlib import Path
import json
import pytz
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import custom modules
sys.path.append('.')  # Ensure the current directory is in the path
from util.TimeConverter import TimeConverter
from util.getERA5Data import download_era5_rainfall, load_download_progress, save_download_progress

class ERA5CityProcessor:
    def __init__(self, city_name, era5_root="G:/002_Data/007_ERA5/000_weather", 
                 processed_dir="data/processed/era5_city", city_data_dir=r"data\debug\input"):
        """
        Initialize ERA5 city data processor
        
        Parameters:
        -----------
        city_name : str
            City name
        era5_root : str
            ERA5 data root directory
        processed_dir : str
            Processed data saving directory
        city_data_dir : str
            City original data directory
        """
        self.city_name = city_name
        self.era5_root = Path(era5_root)
        self.city_data_dir = Path(f"{city_data_dir}/{city_name}")
        self.processed_dir = Path(f"{processed_dir}/{city_name}")
        self.weather_dir = self.processed_dir / 'weather'
        
        # Create necessary directories
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.weather_dir.mkdir(parents=True, exist_ok=True)
        
        # Time converter
        self.time_converter = TimeConverter()
        
        # Progress tracking
        self.progress_file = self.processed_dir / 'era5_processing_progress.json'
        self.processed_dates = self._load_progress()
        
        # Get city timezone
        self.timezone = self._get_city_timezone()
        print(f"Timezone for city {city_name}: {self.timezone}")
        
    def _get_city_timezone(self):
        """Get city timezone"""
        # Here we can query timezone based on city name or coordinates
        # Simplified version: use predefined mapping or default timezone
        # timezone_mapping = {
        #     "london": "Europe/London",
        #     "torino": "Europe/Rome",
        #     "paris": "Europe/Paris",
        #     "augsburg": "Europe/Berlin",
        #     "manchester": "Europe/London",
        #     "toronto": "America/Toronto",
        #     "luzern": "Europe/Zurich",
        #     "marseille": "Europe/Paris",
        #     "cagliari": "Europe/Rome",
        #     "taipeh": "Asia/Taipei",
        #     "essen": "Europe/Berlin",
        #     "darmstadt": "Europe/Berlin",
        #     "innsbruck": "Europe/Vienna",
        #     "strasbourg": "Europe/Paris",
        #     "hamburg": "Europe/Berlin",
        #     "madrid": "Europe/Madrid"
        # }
        timezone_mapping = {
            # Existing mappings from your original data
            "london": "Europe/London",
            "torino": "Europe/Rome",
            "paris": "Europe/Paris",
            "augsburg": "Europe/Berlin",
            "manchester": "Europe/London",
            "toronto": "America/Toronto",
            "luzern": "Europe/Zurich",
            "marseille": "Europe/Paris",
            "cagliari": "Europe/Rome",
            "taipeh": "Asia/Taipei",
            "essen": "Europe/Berlin",
            "darmstadt": "Europe/Berlin",
            "innsbruck": "Europe/Vienna",
            "strasbourg": "Europe/Paris",
            "hamburg": "Europe/Berlin",
            "madrid": "Europe/Madrid",

            # New mappings based on your list
            "constance": "Europe/Berlin",      # Constance (Konstanz), Germany
            "frankfurt": "Europe/Berlin",      # Frankfurt (Frankfurt), Germany
            "losangeles": "America/Los_Angeles", # Los Angeles (Los Angeles), USA
            "bremen": "Europe/Berlin",         # Bremen (Bremen), Germany
            "stuttgart": "Europe/Berlin",      # Stuttgart (Stuttgart), Germany
            "vilnius": "Europe/Vilnius",       # Vilnius (Vilnius), Lithuania
            "groningen": "Europe/Amsterdam",   # Groningen (Groningen), Netherlands
            "zurich": "Europe/Zurich",         # Zurich (Zurich), Switzerland
            "bordeaux": "Europe/Paris",        # Bordeaux (Bordeaux), France
            "wolfsburg": "Europe/Berlin",      # Wolfsburg (Wolfsburg), Germany
            "basel": "Europe/Zurich",          # Basel (Basel), Switzerland
            "toulouse": "Europe/Paris",        # Toulouse (Toulouse), France
            "speyer": "Europe/Berlin",         # Speyer (Speyer), Germany
            "bolton": "Europe/London",         # Bolton (Bolton), UK
            "birmingham": "Europe/London",     # Birmingham (Birmingham), UK
            "rotterdam": "Europe/Amsterdam",   # Rotterdam (Rotterdam), Netherlands
            "kassel": "Europe/Berlin",         # Kassel (Kassel), Germany
            "munich": "Europe/Berlin",         # Munich (Munich), Germany
            "bern": "Europe/Zurich",           # Bern (Bern), Switzerland
            "melbourne": "Australia/Melbourne",# Melbourne (Melbourne), Australia
            "tokyo": "Asia/Tokyo",             # Tokyo (Tokyo), Japan
            "utrecht": "Europe/Amsterdam",     # Utrecht (Utrecht), Netherlands
            "santander": "Europe/Madrid",      # Santander (Santander), Spain
            "graz": "Europe/Vienna"            # Graz (Graz), Austria
        }
        
        return timezone_mapping.get(self.city_name, 'UTC')  # Default to UTC
    
    def _load_progress(self):
        """Load processing progress"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def _save_progress(self, date):
        """Save processing progress"""
        self.processed_dates.add(str(date))
        with open(self.progress_file, 'w') as f:
            json.dump(list(self.processed_dates), f)
    
    def get_target_dates(self):
        """Get list of dates to process"""
        rainfall_file = self.city_data_dir / 'rainfall_data.csv'
        if not rainfall_file.exists():
            print(f"Cannot find rainfall data file: {rainfall_file}")
            # Try to find other possible file names
            alternative_files = list(self.city_data_dir.glob('*rainfall*.csv'))
            if alternative_files:
                rainfall_file = alternative_files[0]
                print(f"Using alternative file: {rainfall_file}")
            else:
                raise FileNotFoundError(f"Cannot find any rainfall data file")
        
        df = pd.read_csv(rainfall_file)
        
        # Check if city column exists
        if 'city' in df.columns:
            dates = df[df['city'] == self.city_name]['date'].unique()
        else:
            # If no city column, assume all data belongs to current city
            dates = df['date'].unique()
        
        return dates
    
    def get_or_create_grid_info(self):
        """Get or create grid information"""
        grid_file = self.weather_dir / 'grid_info.parquet'
        
        if grid_file.exists():
            print(f"Loading existing grid information: {grid_file}")
            return pd.read_parquet(grid_file)
        
        print("Grid information not found, computing from city bounds...")
        # Get city bounds
        # network_file = self.city_data_dir / "selected_network_4326.geojson"
        network_file = self.city_data_dir / "selected_roads.gpkg"
        if not network_file.exists():
            # Try to find other possible file names
            alternative_files = list(self.city_data_dir.glob('*network*4326*.geojson'))
            if alternative_files:
                network_file = alternative_files[0]
                print(f"Using alternative file: {network_file}")
            else:
                raise FileNotFoundError(f"Cannot find city network file")
        
        road_network = gpd.read_file(network_file)
        bounds = road_network.total_bounds  # (minx, miny, maxx, maxy)
        
        # Find a sample ERA5 file to create grid - filter out .idx files
        sample_files = [f for f in list(self.era5_root.glob('era5_rainfall_*.grib')) 
                        if not str(f).endswith('.idx')]
        if not sample_files:
            raise FileNotFoundError("Cannot find any ERA5 GRIB file to create grid")
        
        sample_file = sample_files[0]
        print(f"Using sample file to create grid: {sample_file}")
        
        # Read sample file
        ds_rain = xr.open_dataset(sample_file, engine='cfgrib', 
                                 backend_kwargs={'filter_by_keys': {'edition': 1}})
        
        # Create grid
        grid_gdf = self._create_era5_grid(ds_rain, bounds)
        
        # Save grid info
        grid_gdf.to_parquet(grid_file)
        print(f"Grid information saved to: {grid_file}")
        
        return grid_gdf
    
    def _create_era5_grid(self, ds, city_bounds):
        """Create grid based on ERA5 data"""
        # Get ERA5 lat/lon grid
        lons = ds.longitude.values
        lats = ds.latitude.values
        
        # Create grid polygons
        grid_cells = []
        grid_ids = []
        grid_id = 0
        
        # ERA5 grid resolution
        lon_res = np.abs(lons[1] - lons[0]) if len(lons) > 1 else 0.25
        lat_res = np.abs(lats[1] - lats[0]) if len(lats) > 1 else 0.25
        
        print(f"ERA5 grid resolution: Lon {lon_res:.4f}°, Lat {lat_res:.4f}°")
        print(f"Approximate distance: {lon_res * 111} km x {lat_res * 111} km")
        
        # Process city bounds
        minx, miny, maxx, maxy = city_bounds
        
        # Check longitude range of ERA5 data
        era5_uses_0_to_360 = np.min(lons) >= 0 and np.max(lons) > 180
        print(f"ERA5 data uses 0-360° longitude system: {era5_uses_0_to_360}")
        print(f"ERA5 longitude range: {np.min(lons)} to {np.max(lons)}")
        print(f"Original city bounds longitude range: {minx} to {maxx}")
        
        # Create bounding box containing city
        from shapely.geometry import box
        
        # Format cities that cross the prime meridian
        crosses_prime_meridian = minx < 0 and maxx > 0
        
        if era5_uses_0_to_360:
            if crosses_prime_meridian:
                print(f"City crosses prime meridian, creating two bounding boxes")
                west_box = box(minx + 360, miny, 360, maxy)  # West bounding box
                east_box = box(0, miny, maxx, maxy)          # East bounding box
                city_boxes = [west_box, east_box]
                
                # Debug info
                print(f"West bounding box: [{minx + 360}, {miny}, 360, {maxy}]")
                print(f"East bounding box: [0, {miny}, {maxx}, {maxy}]")
            else:
                # Non-prime meridian crossing city, all converted to 0-360° system
                adj_minx = minx + 360 if minx < 0 else minx
                adj_maxx = maxx + 360 if maxx < 0 else maxx
                city_boxes = [box(adj_minx, miny, adj_maxx, maxy)]
                print(f"Converted city bounds longitude range: {adj_minx} to {adj_maxx}")
        else:
            # ERA5 uses -180 to 180 system
            city_boxes = [box(minx, miny, maxx, maxy)]
            print(f"City bounds longitude range: {minx} to {maxx}")
        
        # Check each lat/lon
        print(f"Start checking {len(lons)}x{len(lats)} = {len(lons)*len(lats)} grid points")
        
        # Store original grid and corresponding standardized grid
        original_grid_cells = []
        standard_grid_cells = []
        
        for lon in lons:
            # Create two possible representations for each longitude value
            lon_360 = lon
            lon_180 = lon if lon <= 180 else lon - 360
            
            for lat in lats:
                # Create grid cell (using original coordinate system)
                cell_minx_orig = lon - lon_res/2
                cell_maxx_orig = lon + lon_res/2
                cell_miny = lat - lat_res/2
                cell_maxy = lat + lat_res/2
                
                original_cell_box = box(cell_minx_orig, cell_miny, cell_maxx_orig, cell_maxy)
                
                # Create -180/180 system representation
                cell_minx_std = lon_180 - lon_res/2
                cell_maxx_std = lon_180 + lon_res/2
                standard_cell_box = box(cell_minx_std, cell_miny, cell_maxx_std, cell_maxy)
                
                # Check for intersection with any city bounding box
                intersects = False
                for city_box in city_boxes:
                    if original_cell_box.intersects(city_box):
                        intersects = True
                        break
                
                if intersects:
                    original_grid_cells.append(original_cell_box)
                    standard_grid_cells.append(standard_cell_box)
                    grid_ids.append(grid_id)
                
                grid_id += 1
        
        # If no intersecting grid found, try expanding bounds
        if len(original_grid_cells) == 0:
            print("Warning: No intersecting grid cell found for city, trying expanded bounds...")
            
            # Expand bounds and retry
            expanded_city_boxes = []
            for city_box in city_boxes:
                bounds = city_box.bounds
                expanded_box = box(
                    bounds[0] - lon_res, 
                    bounds[1] - lat_res, 
                    bounds[2] + lon_res, 
                    bounds[3] + lat_res
                )
                expanded_city_boxes.append(expanded_box)
            
            for lon in lons:
                lon_180 = lon if lon <= 180 else lon - 360
                
                for lat in lats:
                    # Create grid cell for original coordinate system
                    cell_minx_orig = lon - lon_res/2
                    cell_maxx_orig = lon + lon_res/2
                    cell_miny = lat - lat_res/2
                    cell_maxy = lat + lat_res/2
                    
                    original_cell_box = box(cell_minx_orig, cell_miny, cell_maxx_orig, cell_maxy)
                    
                    # Create -180/180 system representation
                    cell_minx_std = lon_180 - lon_res/2
                    cell_maxx_std = lon_180 + lon_res/2
                    standard_cell_box = box(cell_minx_std, cell_miny, cell_maxx_std, cell_maxy)
                    
                    # Check for intersection with any expanded bounding box
                    intersects = False
                    for expanded_box in expanded_city_boxes:
                        if original_cell_box.intersects(expanded_box):
                            intersects = True
                            break
                    
                    if intersects:
                        original_grid_cells.append(original_cell_box)
                        standard_grid_cells.append(standard_cell_box)
                        grid_ids.append(grid_id)
                    
                    grid_id += 1
        
        # Create GeoDataFrame - using standardized (-180 to 180) coordinate system
        grid_gdf = gpd.GeoDataFrame({
            'grid_id': grid_ids,
            'geometry': standard_grid_cells,  # Use standardized geometry data
            'longitude': [p.centroid.x for p in standard_grid_cells],  # Standardized longitude
            'latitude': [p.centroid.y for p in standard_grid_cells],
            'longitude_era5': [p.centroid.x for p in original_grid_cells]  # Save original ERA5 longitude
        }, crs="EPSG:4326")
        
        print(f"Number of intersecting grid cells found for city: {len(standard_grid_cells)}")
        
        # Check conversion success
        print(f"Standardized longitude range: {grid_gdf.geometry.bounds.minx.min():.4f} to {grid_gdf.geometry.bounds.maxx.max():.4f}")
        
        # Visualization validation
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 8))
            grid_gdf.plot(ax=ax, color='pink', edgecolor='black')
            
            # Try to load road data for validation
            try:
                network_file = self.city_data_dir / "roads.gpkg"
                if not network_file.exists():
                    alternative_files = list(self.city_data_dir.glob('*network*4326*.geojson'))
                    if alternative_files:
                        network_file = alternative_files[0]
                
                if network_file.exists():
                    road_network = gpd.read_file(network_file)
                    road_network.plot(ax=ax, color='red', linewidth=0.5)
                    plt.title(f"{self.city_name} ERA5 Grid and Road Network Overlay")
                else:
                    plt.title(f"{self.city_name} ERA5 Grid")
            except Exception as e:
                print(f"Failed to load road data: {str(e)}")
                plt.title(f"{self.city_name} ERA5 Grid")
            
            plt.savefig(self.weather_dir / 'grid_verification.png', dpi=300)
            plt.close()
            print(f"Grid verification plot saved to: {self.weather_dir / 'grid_verification.png'}")
        except Exception as e:
            print(f"Failed to create validation plot: {str(e)}")
        
        return grid_gdf
    
    def ensure_era5_data_available(self, utc_dates_needed):
        """Ensure ERA5 data is available for specified UTC dates"""
        missing_dates = []
        
        for date in utc_dates_needed:
            date_str = date.strftime('%Y-%m-%d')
            # Look for exact matching .grib files, skipping .idx
            grib_files = [f for f in self.era5_root.glob(f"era5_rainfall_{date_str}.grib") 
                         if not str(f).endswith('.idx')]
            
            if not grib_files:
                missing_dates.append(date_str)
        
        # Download missing data
        if missing_dates:
            print(f"Need to download ERA5 data for dates: {missing_dates}")
            self._download_missing_era5_data(missing_dates)
        
        return True
    
    def _download_missing_era5_data(self, missing_dates):
        """Download missing ERA5 data"""
        # Progress file
        progress_file = self.era5_root / 'download_progress.json'
        
        # Load progress
        progress = load_download_progress(str(progress_file))
        downloaded_dates = set(progress['downloaded_dates'])
        
        for date_str in missing_dates:
            # Skip if already downloaded
            if date_str in downloaded_dates:
                print(f"Skip already downloaded date: {date_str}")
                continue
            
            try:
                print(f"Downloading date: {date_str} ERA5 data")
                # Download single day
                download_era5_rainfall(date_str, str(self.era5_root))
                
                # Mark as downloaded
                downloaded_dates.add(date_str)
                save_download_progress(str(progress_file), list(downloaded_dates))
                
            except Exception as e:
                print(f"Error downloading {date_str} data: {str(e)}")
                continue
    
    def get_era5_data_for_local_date(self, local_date):
        """Process data for specified local date"""
        # Convert to datetime
        if isinstance(local_date, str):
            local_date = pd.to_datetime(local_date).date()
        
        local_date_str = local_date.strftime('%Y-%m-%d')
        
        # Check if already processed
        if local_date_str in self.processed_dates:
            print(f"Date {local_date_str} already processed, skipping")
            return
        
        print(f"Processing date: {local_date_str}")
        
        # Get grid info
        grid_info = self.get_or_create_grid_info()
        
        # Generate local hours
        local_hours = pd.date_range(
            start=f"{local_date_str} 00:00",
            end=f"{local_date_str} 23:00",
            freq='H'
        )
        
        # Convert local time to UTC, and collect all required UTC dates
        utc_times = []
        utc_dates_needed = set()
        
        for local_hour in local_hours:
            # Convert local time to UTC
            conversion_result = self.time_converter.local_to_utc(local_hour, self.timezone)
            utc_time = conversion_result['utc_time']
            utc_times.append(utc_time)
            utc_dates_needed.add(utc_time.date())
        # print("local_hours")
        # print(local_hours)
        # print("utc_times")
        # print(utc_times)
        # Ensure all required UTC date data exist
        self.ensure_era5_data_available(utc_dates_needed)
        
        # Get ERA5 data corresponding to each local time point
        all_hourly_data = []
        
        for i, local_hour in enumerate(local_hours):
            utc_time = utc_times[i]
            
            # Get corresponding ERA5 data
            hourly_data = self._get_era5_data_for_time(utc_time, grid_info)
            
            if hourly_data is not None:
                # Add local time info
                # local_time_no_tz = local_hour.tz_localize(None)
                hourly_data['local_time'] = local_hour.strftime('%Y-%m-%d %H:%M:%S')
                # hourly_data['local_time'] = local_hour.tz_localize(None)
                all_hourly_data.append(hourly_data)
            else:
                print(f"Warning: Cannot fetch ERA5 data for local time {local_hour} (UTC: {utc_time})")
        
        # Merge data from all hours
        if all_hourly_data:
            combined_data = pd.concat(all_hourly_data, ignore_index=True)
            
            # Save processed data
            output_file = self.weather_dir / f'local_hourly_rainfall_{local_date_str}.parquet'
            combined_data.to_parquet(output_file)
            print(f"Saved {local_date_str} local time precipitation data to {output_file}")
            
            # Update progress
            self._save_progress(local_date_str)
        else:
            print(f"Warning: {local_date_str} has no valid ERA5 data")
    
    def _get_era5_data_for_time(self, utc_time, grid_info):
        """Get ERA5 data for a specified UTC time"""
        # Get date string
        utc_date_str = utc_time.strftime('%Y-%m-%d')
        
        # Build GRIB file path, ensuring we do not use .idx file
        grib_pattern = self.era5_root / f"era5_rainfall_{utc_date_str}.grib"
        grib_files = [f for f in self.era5_root.glob(grib_pattern.name) 
                     if not str(f).endswith('.idx')]
        
        if not grib_files:
            print(f"Error: Cannot find GRIB file for {utc_date_str}")
            return None
        
        grib_file = grib_files[0]  # Use the first found valid GRIB file
        
        try:
            # Read precipitation data (edition 1)
            ds_rain = xr.open_dataset(grib_file, engine='cfgrib', 
                                     backend_kwargs={'filter_by_keys': {'edition': 1}})
            
            # Get all time points
            era5_times = ds_rain.time.values
            # print("era5_times")
            # print(era5_times)
            
            # Find the starting point of the closest time interval
            # Convert utc_time to np.datetime64 format for comparison
            utc_np_time = np.datetime64(utc_time)
            
            # Find the max time point less than or equal to target time (i.e. closest previous time interval stat point)
            valid_times = era5_times[era5_times <= utc_np_time]
            if len(valid_times) == 0:
                print(f"Error: Cannot find a time interval suitable for {utc_time} in the GRIB file")
                return None
            
            closest_time = valid_times[-1]  # Take the last (closest) time point
            
            # Calculate hour offset
            time_diff = utc_time - pd.Timestamp(closest_time)
            hour_offset = int(time_diff.total_seconds() / 3600)
            
            print(f"Target time: {utc_time}, Closest interval start: {closest_time}, Hour offset: {hour_offset}")
            
            # Ensure hour offset is within valid range (usually 0-11 hours)
            if hour_offset < 0 or hour_offset >= 12:
                print(f"Warning: Calculated hour offset ({hour_offset}) is out of expected range (0-11)")
                if hour_offset >= 12:
                    print(f"Try to find next time interval")
                    # May need to check next day's data
                    next_day_utc = utc_time + pd.Timedelta(days=1)
                    next_day_str = next_day_utc.strftime('%Y-%m-%d')
                    next_grib_pattern = self.era5_root / f"era5_rainfall_{next_day_str}.grib"
                    next_grib_files = [f for f in self.era5_root.glob(next_grib_pattern.name) 
                                     if not str(f).endswith('.idx')]
                    
                    if not next_grib_files:
                        print(f"Error: Cannot find {next_day_str} GRIB file")
                        return None
                    
                    try:
                        ds_next = xr.open_dataset(next_grib_files[0], engine='cfgrib', 
                                               backend_kwargs={'filter_by_keys': {'edition': 1}})
                        era5_times_next = ds_next.time.values
                        for t in era5_times_next:
                            if t > utc_np_time:
                                closest_time = t
                                time_diff = utc_time - pd.Timestamp(closest_time)
                                hour_offset = int(time_diff.total_seconds() / 3600)
                                if 0 <= hour_offset < 12:
                                    print(f"Found suitable time interval on next day: {closest_time}, New hour offset: {hour_offset}")
                                    ds_rain = ds_next  # Use new dataset
                                    break
                    except Exception as e:
                        print(f"Error reading next day's data: {str(e)}")
            
            # Extract data slice for that time point
            time_slice = ds_rain.sel(time=closest_time)
            
            # Collect data for all grids
            grid_data = []
            
            for _, grid_cell in grid_info.iterrows():
                # Get data for that grid cell
                cell_data = time_slice.sel(
                    longitude=grid_cell.longitude,
                    latitude=grid_cell.latitude,
                    method='nearest'
                )
                
                # Get precipitation type data
                try:
                    ds_type = xr.open_dataset(grib_file, engine='cfgrib',
                                            backend_kwargs={'filter_by_keys': {'edition': 2}})
                    type_data = ds_type.sel(
                        time=closest_time,
                        longitude=grid_cell.longitude,
                        latitude=grid_cell.latitude,
                        method='nearest'
                    )
                    # print("type_data")
                    # print(type_data.ptype.values)
                    
                    if hasattr(type_data, 'ptype'):
                        if type_data.ptype.values.size > hour_offset:
                            precip_type = float(type_data.ptype.values[hour_offset])
                            if np.isnan(precip_type):
                                precip_type = 0
                        elif type_data.ptype.values.size == 1:
                            precip_type = float(type_data.ptype.values.item())
                        else:
                            print(f"Warning: type_data.ptype.values size ({type_data.ptype.values.size}) is less than hour offset ({hour_offset})")
                            precip_type = 0.0
                    else:
                        precip_type = -1
                        
                    ds_type.close()
                except Exception as e:
                    precip_type = -1
                
                # Safely extract tp and lsrr values - accounting for array format data
                try:
                    # Process tp value - use calculated hour offset
                    if hasattr(cell_data, 'tp'):
                        tp_values = cell_data.tp.values
                        if tp_values.size > hour_offset:
                            tp_value = float(tp_values[hour_offset])
                        elif tp_values.size == 1:
                            tp_value = float(tp_values.item())
                        else:
                            print(f"Warning: tp_values size ({tp_values.size}) is less than hour offset ({hour_offset})")
                            tp_value = 0.0
                    else:
                        tp_value = 0.0
                    
                    # Process lsrr value - use calculated hour offset
                    if hasattr(cell_data, 'lsrr'):
                        lsrr_values = cell_data.lsrr.values
                        if lsrr_values.size > hour_offset:
                            lsrr_value = float(lsrr_values[hour_offset])
                        elif lsrr_values.size == 1:
                            lsrr_value = float(lsrr_values.item())
                        else:
                            print(f"Warning: lsrr_values size ({lsrr_values.size}) is less than hour offset ({hour_offset})")
                            lsrr_value = 0.0
                    else:
                        lsrr_value = 0.0
                
                except Exception as e:
                    print(f"Error extracting precipitation data: {str(e)}")
                    tp_value = 0.0
                    lsrr_value = 0.0
                
                # Append to results
                grid_data.append({
                    'utc_time': utc_time.tz_localize('UTC'),  # Use original target UTC time
                    'grid_id': grid_cell.grid_id,
                    'longitude': grid_cell.longitude,
                    'latitude': grid_cell.latitude,
                    'total_precipitation': tp_value if not np.isnan(tp_value) else 0.0,
                    'large_scale_rain_rate': lsrr_value if not np.isnan(lsrr_value) else 0.0,
                    'precipitation_type': precip_type
                })
            
            # Create DataFrame
            return pd.DataFrame(grid_data)
            
        except Exception as e:
            print(f"Error processing ERA5 data for {utc_time}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_all_dates(self):
        """Process data for all target dates"""
        target_dates = self.get_target_dates()
        
        for date in target_dates:
            try:
                # Ensure date format is correct
                formatted_date = pd.to_datetime(date).strftime('%Y-%m-%d')
                self.get_era5_data_for_local_date(formatted_date)
            except Exception as e:
                print(f"Error processing date {date}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"All dates for city {self.city_name} processed!")

def main():
    # Set data directories
    city_dir = Path(r'data\debug\input')
    era5_root = Path(r"G:\002_Data\007_ERA5\000_weather")
    output_dir = Path(r'data\debug\output\city_whole')
    
    # Create global progress file
    global_progress_file = Path(r'data\debug\output\global_era5_processing_progress.json')
    
    # Load global progress
    processed_cities = set()
    if global_progress_file.exists():
        with open(global_progress_file, 'r') as f:
            processed_cities = set(json.load(f))
    
    # Get all cities
    cities = [city for city in os.listdir(city_dir) if (city_dir / city).is_dir()]
    
    # Show overall progress
    total_cities = len(cities)
    processed_count = len(processed_cities)
    print(f"Total cities: {total_cities}")
    print(f"Processed cities: {processed_count}")
    print(f"Remaining cities: {total_cities - processed_count}")
    
    try:
        for city in cities:
            if city in processed_cities:
                print(f"\nCity {city} already processed, skipping")
                continue
            
            print(f"\nStarting to process city: {city} ({len(processed_cities) + 1}/{total_cities})")
            try:
                processor = ERA5CityProcessor(city, era5_root, output_dir, city_dir)
                processor.process_all_dates()
                
                # Update and save global progress
                processed_cities.add(city)
                with open(global_progress_file, 'w') as f:
                    json.dump(list(processed_cities), f)
                
                print(f"City {city} processing complete")
                
            except Exception as e:
                print(f"Error processing city {city}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
            
    except KeyboardInterrupt:
        print("\nUser interruption detected, saving progress and exiting...")
        with open(global_progress_file, 'w') as f:
            json.dump(list(processed_cities), f)
        sys.exit(0)
    
    print("\nAll cities processed!")

if __name__ == "__main__":
    main() 