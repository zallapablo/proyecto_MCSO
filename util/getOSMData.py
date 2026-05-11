import os
import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box
import argparse

def get_bounding_box_from_links(links_df):
    """Get the bounding box for all points from links.csv"""
    # Create a list of point geometries
    points = [Point(row['long'], row['lat']) for _, row in links_df.iterrows()]
    # Create a GeoDataFrame
    points_gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:4326")
    # Get bounding box
    minx, miny, maxx, maxy = points_gdf.total_bounds
    # Expand bounding box (e.g., by 10%) to ensure surrounding roads are included
    dx = (maxx - minx) * 0.1
    dy = (maxy - miny) * 0.1
    bbox = box(minx - dx, miny - dy, maxx + dx, maxy + dy)
    return bbox

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download and process OSM road data for cities.")
    parser.add_argument('--city_folder', type=str, default=r'data\debug\input', help="Directory containing the city folders")
    args = parser.parse_args()

    city_folder_path = args.city_folder
    cities = [name for name in os.listdir(city_folder_path) if os.path.isdir(os.path.join(city_folder_path, name))]

    # download road data for each city
    for city in cities:
        # create folder for each city
        folder_name = os.path.join(city_folder_path, city)
        file_path = os.path.join(folder_name, 'roads.gpkg')
        print("processing", city)
            
        # Download road data if it doesn't exist
        if not os.path.exists(file_path):
            try:
                G = ox.graph_from_place(city, network_type='all')
                ox.save_graph_geopackage(G, filepath=file_path, encoding='utf-8')
                print(f"{city} saved to {file_path}")
            except Exception as e:
                print(f"can not get {city}'s road data: {e}")
                continue
        else:
            print(f"{city} saved to {file_path}")

        try:
            # Read links.csv file
            links_path = os.path.join(folder_name, 'links.csv')
            if not os.path.exists(links_path):
                print(f"links.csv not found for {city}")
                continue
                
            links_df = pd.read_csv(links_path)
            
            # Get bounding box
            bbox = get_bounding_box_from_links(links_df)
            
            # Read road data
            roads_gdf = gpd.read_file(file_path, layer='edges')
            roads_gdf.set_crs(epsg=4326, inplace=True)
            
            # Filter roads using the bounding box
            selected_roads = roads_gdf[roads_gdf.geometry.intersects(bbox)].copy()
            
            # Save the filtered road data
            selected_file_path = os.path.join(folder_name, 'selected_roads.gpkg')
            selected_roads.to_file(selected_file_path, driver='GPKG')
            print(f"Selected roads saved to {selected_file_path}")
            
            # Convert coordinate reference system and save as shp file
            out_dir = os.path.join(folder_name, "selected_roads_32650")
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
                
            # Convert CRS
            selected_roads.to_crs(epsg=32650, inplace=True)
            
            # Save as shapefile
            shp_path = os.path.join(out_dir, 'selected_roads_32650.shp')
            if not os.path.exists(shp_path):
                selected_roads.to_file(shp_path, driver='ESRI Shapefile')
                print(f"Shapefile saved to {shp_path}")
            else:
                print(f"{city} shapefile already exists")
                
        except Exception as e:
            print(f"Error processing {city}: {e}")

