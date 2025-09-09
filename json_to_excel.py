import os
import json
import pandas as pd
from pathlib import Path


def process_json_files_to_excel(directory_path, output_excel_path):
    json_files = []
    directory = Path(directory_path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory {directory_path} does not exist")

    # Find all json like {id}.json
    for file_path in directory.glob("*.json"):
        json_files.append(file_path)

    if not json_files:
        print(f"No JSON files found in {directory_path}")
        return

    print(f"Found {len(json_files)} JSON files")

    extracted_data = []

    for json_file in json_files:
        try:
            file_id = json_file.stem

            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            try:
                # products > {id}
                product_data = data.get('products', {}).get(file_id, {})

                if not product_data:
                    print(f"Warning: No product data found for ID {file_id} in {json_file.name}")
                    continue

                product_name = product_data.get('name', '')
                features = product_data.get('features', {})
                producer = product_data.get('producer', {}).get('name', '')
                xkom_category = product_data.get('category', {}).get('parentCategoryName', '')

                features_str = json.dumps(features, ensure_ascii=False) if features else ''

                price_info = product_data.get('priceInfo', {})
                price = price_info.get('price', 0.0)

                # Cast to float to fix error
                try:
                    price = float(price) if price is not None else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                    print(f"Warning: Invalid price format for {file_id}, set to 0.0")

                product_description = product_data.get('productDescription', '')

                extracted_data.append({
                    'id': file_id,
                    'producer': producer,
                    'productName': product_name,
                    'xkomCategory': xkom_category,
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

    if extracted_data:
        df = pd.DataFrame(extracted_data)

        # put features and product desc at the end because its log
        df = df[['id', 'producer', 'productName', 'price', 'xkomCategory', 'features', 'productDescription']]
        df = df.sort_values(by=['xkomCategory'])

        try:
            df.to_excel(output_excel_path, index=False, engine='openpyxl')
            print(f"\nSuccessfully exported {len(extracted_data)} records to {output_excel_path}")
            print(f"Columns: {list(df.columns)}")
        except Exception as e:
            print(f"Error writing to Excel file: {e}")
    else:
        print("No data extracted. Excel file not created.")


if __name__ == "__main__":
    directory_path = "./product_data_json/"
    output_excel_path = "products_data.xlsx"

    try:
        process_json_files_to_excel(directory_path, output_excel_path)
    except Exception as e:
        print(f"Error: {e}")