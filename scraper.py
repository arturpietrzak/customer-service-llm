import os
import json
import pandas as pd
from pathlib import Path


def process_json_files_to_excel(directory_path, output_excel_path):
    """
    Process JSON files from a directory and export data to Excel.

    Args:
        directory_path (str): Path to directory containing JSON files
        output_excel_path (str): Path for output Excel file
    """

    # Get list of JSON files in the directory
    json_files = []
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory {directory_path} does not exist")

    # Find all JSON files matching the pattern {id}.json
    for file_path in directory.glob("*.json"):
        json_files.append(file_path)

    if not json_files:
        print(f"No JSON files found in {directory_path}")
        return

    print(f"Found {len(json_files)} JSON files")

    # List to store extracted data
    extracted_data = []

    # Process each JSON file
    for json_file in json_files:
        try:
            # Extract ID from filename (remove .json extension)
            file_id = json_file.stem

            # Read and parse JSON file
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract required fields
            try:
                # Navigate to products > {id}
                product_data = data.get('products', {}).get(file_id, {})

                if not product_data:
                    print(f"Warning: No product data found for ID {file_id} in {json_file.name}")
                    continue

                # Extract fields
                product_name = product_data.get('name', '')
                features = product_data.get('features', {})

                # Convert features to string (JSON format)
                features_str = json.dumps(features, ensure_ascii=False) if features else ''

                # Extract price from priceInfo
                price_info = product_data.get('priceInfo', {})
                price = price_info.get('price', 0.0)

                # Ensure price is float
                try:
                    price = float(price) if price is not None else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                    print(f"Warning: Invalid price format for {file_id}, set to 0.0")

                product_description = product_data.get('productDescription', '')

                # Add to extracted data
                extracted_data.append({
                    'id': file_id,
                    'productName': product_name,
                    'features': features_str,
                    'price': price,
                    'productDescription': product_description
                })

                print(f"Successfully processed {json_file.name}")

            except KeyError as e:
                print(f"Error extracting data from {json_file.name}: Missing key {e}")
                continue

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file {json_file.name}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
            continue

    # Create DataFrame and export to Excel
    if extracted_data:
        df = pd.DataFrame(extracted_data)

        # Reorder columns to match requirements
        df = df[['id', 'productName', 'features', 'price', 'productDescription']]

        # Export to Excel
        try:
            df.to_excel(output_excel_path, index=False, engine='openpyxl')
            print(f"\nSuccessfully exported {len(extracted_data)} records to {output_excel_path}")
            print(f"Columns: {list(df.columns)}")
        except Exception as e:
            print(f"Error writing to Excel file: {e}")
    else:
        print("No data extracted. Excel file not created.")


# Example usage
if __name__ == "__main__":
    # Set your directory path here
    directory_path = r"./product_data_json/"  # Replace with your actual path
    output_excel_path = "products_data_1.xlsx"

    # Alternative: Use current directory
    # directory_path = "."

    try:
        process_json_files_to_excel(directory_path, output_excel_path)
    except Exception as e:
        print(f"Script execution failed: {e}")