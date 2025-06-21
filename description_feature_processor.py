import pandas as pd
import google.generativeai as genai
import time
import os
from typing import Optional


class ExcelGeminiProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')

    def process_features(self, features_text: str) -> str:
        if pd.isna(features_text) or not features_text.strip():
            return ""

        prompt = f"Z poniższego tekstu w formacie JSON stwórz zwykły teskt. Zwróć sam tekst: {features_text}"

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error processing features: {e}")
            return features_text  # original text if API fails

    def process_description(self, description_text: str) -> str:
        if pd.isna(description_text) or not description_text.strip():
            return ""

        prompt = f"Poniższy tekst zawiera różne elementy HTML. Oczyść ten tekst. Zwróć sam tekst: {description_text}"

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error processing description: {e}")
            return description_text  # original text if API fails

    def load_or_create_output_file(self, input_file: str, output_file: str) -> pd.DataFrame:
        # If output file is found load it
        if os.path.exists(output_file):
            try:
                df = pd.read_excel(output_file)
                return df
            except Exception as e:
                print(f"Error loading existing output file: {e}")

        # Else create new file
        try:
            df = pd.read_excel(input_file)
            df['_features_processed'] = False
            df['_description_processed'] = False
            return df
        except Exception as e:
            print(f"Error reading input Excel file: {e}")

    def save_progress(self, df: pd.DataFrame, output_file: str):
        try:
            save_df = df.copy()

            # Remove progress columns
            tracking_cols = [col for col in save_df.columns if col.startswith('_')]
            save_df = save_df.drop(columns=tracking_cols)

            save_df.to_excel(output_file, index=False)
            print(f"Progress saved to: {output_file}")
        except Exception as e:
            print(f"Error saving progress: {e}")

    def find_next_unprocessed_row(self, df: pd.DataFrame, start_row: int = 0) -> int:
        if '_features_processed' not in df.columns:
            df['_features_processed'] = False
        if '_description_processed' not in df.columns:
            df['_description_processed'] = False

        for i in range(start_row, len(df)):
            if not df.at[i, '_features_processed'] or not df.at[i, '_description_processed']:
                return i
        return -1

    def process_excel_file(self, input_file: str, output_file: str, start_row: int = 0, delay: float = 1.0):
        df = self.load_or_create_output_file(input_file, output_file)

        # Verify columns
        required_columns = ['id', 'producer', 'productName', 'price', 'xkomCategory', 'features', 'productDescription']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            return

        # print(f"Total rows in file: {len(df)}")

        actual_start = self.find_next_unprocessed_row(df, start_row)

        if actual_start == -1:
            print("All rows have been processed!")
            return

        print(f"Starting processing from row {actual_start + 1} (index {actual_start})")

        # Process each row , begin from start_row
        for index in range(actual_start, len(df)):
            row = df.iloc[index]
            print(f"\nProcessing row {index + 1}/{len(df)} (ID: {row['id']})")

            if not df.at[index, '_features_processed']:
                try:
                    processed_features = self.process_features(str(row['features']))
                    df.at[index, 'features'] = processed_features
                    df.at[index, '_features_processed'] = True
                    print("  - Features processed successfully")
                    self.save_progress(df, output_file)
                    time.sleep(delay)
                except Exception as e:
                    print(f"  - Error processing features: {e}")
                    continue
            else:
                print("  - Features already processed, skipping")

            if not df.at[index, '_description_processed']:
                print("  - Processing product description...")
                try:
                    processed_description = self.process_description(str(row['productDescription']))
                    df.at[index, 'productDescription'] = processed_description
                    df.at[index, '_description_processed'] = True
                    print("  - Description processed successfully")
                    self.save_progress(df, output_file)
                    time.sleep(delay)
                except Exception as e:
                    print(f"  - Error processing description: {e}")
                    continue
            else:
                print("  - Description already processed, skipping")

            print(f"  - Completed row {index + 1}")

        self.save_progress(df, output_file)
        print("Processing completed successfully")

    # def get_processing_status(self, output_file: str):
    #     if not os.path.exists(output_file):
    #         print(f"Output file {output_file} does not exist yet.")
    #         return
    #     try:
    #         df = pd.read_excel(output_file)
    #         total_rows = len(df)
    #         if '_features_processed' in df.columns and '_description_processed' in df.columns:
    #             features_processed = df['_features_processed'].sum()
    #             descriptions_processed = df['_description_processed'].sum()
    #             fully_processed = (df['_features_processed'] & df['_description_processed']).sum()
    #             print(f"Processing Status for {output_file}:")
    #             print(f"Total rows: {total_rows}")
    #             print(f"Features processed: {features_processed}/{total_rows}")
    #             print(f"Descriptions processed: {descriptions_processed}/{total_rows}")
    #             print(f"Fully processed rows: {fully_processed}/{total_rows}")
    #             next_unprocessed = self.find_next_unprocessed_row(df, 0)
    #             if next_unprocessed != -1:
    #                 print(f"Next unprocessed row: {next_unprocessed + 1} (index {next_unprocessed})")
    #             else:
    #                 print("All rows have been processed!")
    #         else:
    #             print(f"File has {total_rows} rows, but no processing status available.")
    #     except Exception as e:
    #         print(f"Error reading status: {e}")


def main():
    API_KEY = ""  
    INPUT_FILE = "products_data_1_processed.xlsx"  
    OUTPUT_FILE = "processed_products_data_2_processed.xlsx"  
    START_ROW = 166  
    DELAY_BETWEEN_CALLS = 6.0  

    processor = ExcelGeminiProcessor(API_KEY)
    # processor.get_processing_status(OUTPUT_FILE)
    print(f"Starting processing from row {START_ROW + 1}...")
    processor.process_excel_file(INPUT_FILE, OUTPUT_FILE, START_ROW, DELAY_BETWEEN_CALLS)


if __name__ == "__main__":
    main()