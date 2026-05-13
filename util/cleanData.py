import os
import shutil
from pathlib import Path

def clean_era5_city_folders(base_dir="data/processed/era5_city", dry_run=True):
    """
    Clean era5_city folders, keeping only the grid_info.parquet file for each city
    
    Parameters:
    base_dir: base directory path
    dry_run: if True, just shows what would be deleted, but does not actually delete
    """
    base_path = Path(base_dir)
    
    # Ensure base directory exists
    if not base_path.exists():
        print(f"Error: Directory {base_dir} does not exist")
        return
    
    # Get all city folders
    city_folders = [f for f in base_path.iterdir() if f.is_dir()]
    
    if not city_folders:
        print(f"No city folders found in {base_dir}")
        return
    
    print(f"Found {len(city_folders)} city folders")
    
    # Track deletion statistics
    deleted_files = 0
    deleted_folders = 0
    preserved_files = 0
    
    # Iterate through each city folder
    for city_folder in city_folders:
        city_name = city_folder.name
        print(f"\nProcessing city: {city_name}")
        
        # File path to keep
        grid_info_path = city_folder / "weather" / "grid_info.parquet"
        
        # Check if grid_info.parquet exists
        grid_info_exists = grid_info_path.exists()
        if grid_info_exists:
            preserved_files += 1
            print(f"  Keeping file: {grid_info_path}")
        else:
            print(f"  Warning: {grid_info_path} does not exist")
        
        # Iterate through all files and directories in the city folder
        for root, dirs, files in os.walk(city_folder, topdown=False):  # topdown=False ensures subdirectories are processed first
            root_path = Path(root)
            
            # Process files
            for file in files:
                file_path = root_path / file
                
                # Delete if it is not the file to keep
                if file_path != grid_info_path:
                    if dry_run:
                        print(f"  Will delete file: {file_path}")
                    else:
                        try:
                            file_path.unlink()
                            print(f"  Deleted file: {file_path}")
                            deleted_files += 1
                        except Exception as e:
                            print(f"  Error deleting file {file_path}: {str(e)}")
            
            # Process directories
            # Do not delete weather directory and the city directory itself
            if (root_path != city_folder and 
                root_path != city_folder / "weather" and
                (not grid_info_exists or "weather" not in root_path.parts)):
                
                # Check if directory is empty
                if not any(root_path.iterdir()) or not grid_info_exists:
                    if dry_run:
                        print(f"  Will delete directory: {root_path}")
                    else:
                        try:
                            # Use rmdir to only delete empty directories
                            root_path.rmdir()
                            print(f"  Deleted directory: {root_path}")
                            deleted_folders += 1
                        except Exception as e:
                            print(f"  Error deleting directory {root_path}: {str(e)}")
        
        # Ensure weather directory exists
        weather_dir = city_folder / "weather"
        if not weather_dir.exists() and not dry_run:
            weather_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Created directory: {weather_dir}")
    
    # Print statistics
    print("\nCleanup complete!")
    print(f"Estimated to delete {deleted_files} files and {deleted_folders} directories" if dry_run 
          else f"Deleted {deleted_files} files and {deleted_folders} directories")
    print(f"Preserved {preserved_files} grid_info.parquet files")

if __name__ == "__main__":
    # First do a dry run to show what will be deleted
    print("=== Execution preview mode (will not actually delete files) ===")
    clean_era5_city_folders(dry_run=True)
    
    # Ask user to confirm
    response = input("\nConfirm deletion of these files? (yes/no): ").strip().lower()
    if response == 'yes':
        print("\n=== Executing actual deletion ===")
        clean_era5_city_folders(dry_run=False)
    else:
        print("Operation cancelled, no files were deleted.")
