import os
import glob
import shutil
from pathlib import Path
import time

def reset_progress(data_root, 
                   delete_progress_files=False, 
                   delete_parquet_files=False, 
                   delete_metadata_files=False,
                   delete_detectors_files=False,
                   dry_run=False):
    """
    Reset processing progress and delete related files as needed
    
    Arguments:
    - data_root: Data root directory
    - delete_progress_files: Whether to delete progress files
    - delete_parquet_files: Whether to delete generated parquet files
    - delete_metadata_files: Whether to delete generated metadata files
    - delete_detectors_files: Whether to delete generated detectors files
    - dry_run: If True, only show files that would be deleted without actually deleting
    """
    
    print("=== Progress Reset Tool ===")
    print(f"Data root directory: {data_root}")
    print(f"Mode: {'Preview Mode (Will not actually delete files)' if dry_run else 'Execution Mode (Will delete files)'}")
    print("Will perform the following operations:")
    print(f"- Delete progress files: {delete_progress_files}")
    print(f"- Delete Parquet files: {delete_parquet_files}")
    print(f"- Delete metadata files: {delete_metadata_files}")
    print(f"- Delete detectors files: {delete_detectors_files}")
    print("-" * 40)
    
    # Get all city folders
    city_folders = [d for d in glob.glob(os.path.join(data_root, "*")) if os.path.isdir(d)]
    print(f"Found {len(city_folders)} city folders")
    
    files_to_delete = []
    
    # Collect progress files
    if delete_progress_files:
        progress_files = [
            os.path.join(data_root, "hourly_processing_progress.txt"),
            os.path.join(data_root, "csv2parquet_progress.txt"),
            os.path.join(data_root, "road2grid_progress.txt"),
            os.path.join(data_root, "detectors_processing_progress.txt")
        ]
        
        for file_path in progress_files:
            if os.path.exists(file_path):
                files_to_delete.append(file_path)
                print(f"Will delete progress file: {file_path}")
    
    # Collect Parquet files for each city
    if delete_parquet_files:
        for city_folder in city_folders:
            city_name = os.path.basename(city_folder)
            
            # Find various possible parquet files
            parquet_patterns = [
                # "hourly_readings.parquet",
                # "sensor_readings.parquet", 
                # "roads.parquet",
                # "selected_network.parquet",
                # "5min_readings.parquet",
                "detectors.parquet"
            ]
            
            for pattern in parquet_patterns:
                file_path = os.path.join(city_folder, pattern)
                if os.path.exists(file_path):
                    files_to_delete.append(file_path)
                    print(f"Will delete Parquet file: {file_path}")
    
    # Collect metadata files
    if delete_metadata_files:
        for city_folder in city_folders:
            city_name = os.path.basename(city_folder)
            metadata_file = os.path.join(city_folder, f"{city_name}_metadata.json")
            
            if os.path.exists(metadata_file):
                files_to_delete.append(metadata_file)
                print(f"Will delete metadata file: {metadata_file}")
    
    # Execute deletion
    if not dry_run:
        if not files_to_delete:
            print("No files to delete found.")
        else:
            print(f"\nPreparing to delete {len(files_to_delete)} files...")
            
            # Give user a final chance to confirm
            confirm = input("Confirm deleting above files? (y/n): ").strip().lower()
            
            if confirm == 'y':
                deleted_count = 0
                for file_path in files_to_delete:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"Deleted: {file_path}")
                    except Exception as e:
                        print(f"Failed to delete {file_path}: {str(e)}")
                
                print(f"\nComplete! Successfully deleted {deleted_count}/{len(files_to_delete)} files.")
            else:
                print("Operation cancelled.")
    else:
        print(f"\nPreview mode: {len(files_to_delete)} files would be deleted.")
    
    return len(files_to_delete)

def main():
    # Configuration area - modify these values as needed
    # ===================================================================
    DATA_ROOT = "data/001_Integrated Urban Traffic-Flood Dataset"
    
    # Set to True to delete corresponding files, False to keep them
    DELETE_PROGRESS_FILES = False      # Delete all progress tracking files
    DELETE_PARQUET_FILES = True      # Delete generated parquet files
    DELETE_METADATA_FILES = False      # Delete generated metadata files
    # DELETE_DETECTORS_FILES = True     # Delete generated detectors files
    
    DRY_RUN = False   # Set to True for preview without actual deletion
    # ===================================================================
    
    reset_progress(
        data_root=DATA_ROOT,
        delete_progress_files=DELETE_PROGRESS_FILES,
        delete_parquet_files=DELETE_PARQUET_FILES,
        delete_metadata_files=DELETE_METADATA_FILES,
        # delete_detectors_files=DELETE_DETECTORS_FILES,
        dry_run=DRY_RUN
    )

if __name__ == "__main__":
    main() 