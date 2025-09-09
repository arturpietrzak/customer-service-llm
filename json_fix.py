import pandas as pd
import json
import sys
from pathlib import Path

def process_features_json(json_string):
    try:
        features = json.loads(json_string)

        processed_features = []
        for feature in features:
            processed_feature = {
                'key': feature.get('key'),
                'values': feature.get('values', [])
            }
            processed_features.append(processed_feature)

        return json.dumps(processed_features, ensure_ascii=False)

    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        print(f"Error processing JSON: {e}")
        return json_string

def process_excel_file(input_file_path):
    try:
        df = pd.read_excel(input_file_path)

        if 'features' not in df.columns:
            print("Error: 'features' column not found in the Excel file.")
            print(f"Available columns: {list(df.columns)}")
            return False

        print("Processing features column...")
        df['features'] = df['features'].apply(lambda x: process_features_json(x) if pd.notna(x) else x)

        input_path = Path(input_file_path)
        output_file_path = input_path.parent / f"{input_path.stem}_processed{input_path.suffix}"

        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)

        print(f"File processed successfully! Saved as: {output_file_path}")

        return True

    except Exception as e:
        print(f"Error processing file: {e}")
        return False

if __name__ == "__main__":
    process_excel_file("./products_data_1.xlsx")
