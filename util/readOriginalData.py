import pandas as pd
import os
import dask.dataframe as dd
import argparse

def process_links_and_detectors(in_dir, out_dir):
    """Process links.csv and detectors_public.csv, and split the data by city code.

    Args:
        in_dir (str): Input directory.
        out_dir (str): Output directory.
    """
    links_df = pd.read_csv(os.path.join(in_dir, 'links.csv'))
    detectors_df = pd.read_csv(os.path.join(in_dir, 'detectors_public.csv'))

    city_codes = set(links_df['citycode']).union(set(detectors_df['citycode']))

    for city_code in city_codes:
        folder_name = os.path.join(out_dir, str(city_code))  # Ensure city_code is converted to string
        os.makedirs(folder_name, exist_ok=True)  # Use exist_ok=True to avoid errors if folder exists

        links_city_df = links_df[links_df['citycode'] == city_code]
        detectors_city_df = detectors_df[detectors_df['citycode'] == city_code]

        links_city_df.to_csv(os.path.join(folder_name, 'links.csv'), index=False)
        detectors_city_df.to_csv(os.path.join(folder_name, 'detectors_public.csv'), index=False)

        print(f"Data saved to {folder_name}")

def process_utd_data(in_path, out_dir, target_cities=None):
    """Process utd19_u.csv and split the data by city.

    Args:
        in_path (str): Input file path.
        out_dir (str): Output directory.
        target_cities (list): Optional list of specific cities to process.
    """
    df = dd.read_csv(in_path, assume_missing=True, dtype={'detid': str})
    
    if target_cities:
        # Filter Dask dataframe before computing unique cities or saving
        df = df[df['city'].isin(target_cities)]

    cities = df['city'].unique().compute()

    for city in cities:
        city_df = df[df['city'] == city]
        out_path = os.path.join(out_dir, str(city), f'{city}_sensor.csv')  # Ensure city is converted to string
        os.makedirs(os.path.dirname(out_path), exist_ok=True) # Use exist_ok=True to avoid errors if folder exists
        city_df.to_csv(out_path, single_file=True)
        print(f'{city}_data.csv has been saved!')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process and split original traffic data by city.")
    parser.add_argument('--in_dir', type=str, default=r'.\data\eth_dataset', help="Input directory containing original datasets")
    parser.add_argument('--out_dir', type=str, default=r'.\data\debug\input', help="Output directory to save processed city data")
    parser.add_argument('--cities', type=str, nargs='+', default=['madrid', 'santander'], help="Specific cities to extract")
    args = parser.parse_args()

    in_path_utd = os.path.join(args.in_dir, 'utd19_u.csv')

    process_links_and_detectors(args.in_dir, args.out_dir)
    print("process_links_and_detectors done!!!!!!!!!!")
    
    cities_to_extract = [c.lower() for c in args.cities] if args.cities else None
    process_utd_data(in_path_utd, args.out_dir, target_cities=cities_to_extract)
    print("process_utd_data done!!!!!!!!!!")