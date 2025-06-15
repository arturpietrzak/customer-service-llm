import pandas as pd
import google.generativeai as genai
import time
import os
from typing import Optional


class ExcelGeminiProcessor:
    def __init__(self, api_key: str):
        """
        Initialize the processor with Gemini API key.

        Args:
            api_key (str): Your Gemini API key
        """
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def process_features(self, features_text: str) -> str:
        """
        Process features text using Gemini API.

        Args:
            features_text (str): Raw features text

        Returns:
            str: Processed features text
        """
        if pd.isna(features_text) or not features_text.strip():
            return ""

        prompt = f"Z poniższego tekstu w formacie JSON stwórz zwykły teskt. Zwróć sam tekst: {features_text}"

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error processing features: {e}")
            return features_text  # Return original text if API call fails

    def process_description(self, description_text: str) -> str:
        """
        Process product description using Gemini API.

        Args:
            description_text (str): Raw product description

        Returns:
            str: Cleaned product description
        """
        if pd.isna(description_text) or not description_text.strip():
            return ""

        prompt = f"Oczyść ten tekst. Zwróć sam tekst: {description_text}"

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error processing description: {e}")
            return description_text  # Return original text if API call fails

    def load_or_create_output_file(self, input_file: str, output_file: str) -> pd.DataFrame:
        """
        Load existing output file if it exists, otherwise create from input file.

        Args:
            input_file (str): Path to input Excel file
            output_file (str): Path to output Excel file

        Returns:
            pd.DataFrame: DataFrame to work with
        """
        if os.path.exists(output_file):
            print(f"Loading existing output file: {output_file}")
            try:
                df = pd.read_excel(output_file)
                print(f"Loaded existing file with {len(df)} rows")
                return df
            except Exception as e:
                print(f"Error loading existing output file: {e}")
                print("Creating new output file from input...")

        # Load from input file
        print(f"Creating new output file from input: {input_file}")
        try:
            df = pd.read_excel(input_file)
            # Add processing status columns to track what's been processed
            df['_features_processed'] = False
            df['_description_processed'] = False
            return df
        except Exception as e:
            print(f"Error reading input Excel file: {e}")
            raise

    def save_progress(self, df: pd.DataFrame, output_file: str):
        """
        Save current progress to file.

        Args:
            df (pd.DataFrame): Current dataframe
            output_file (str): Path to output file
        """
        try:
            # Create a copy for saving (without internal tracking columns)
            save_df = df.copy()

            # Remove internal tracking columns before saving
            tracking_cols = [col for col in save_df.columns if col.startswith('_')]
            save_df = save_df.drop(columns=tracking_cols)

            save_df.to_excel(output_file, index=False)
            print(f"Progress saved to: {output_file}")
        except Exception as e:
            print(f"Error saving progress: {e}")

    def find_next_unprocessed_row(self, df: pd.DataFrame, start_row: int = 0) -> int:
        """
        Find the next row that needs processing.

        Args:
            df (pd.DataFrame): DataFrame to check
            start_row (int): Row index to start checking from

        Returns:
            int: Index of next unprocessed row, or -1 if all processed
        """
        # Add tracking columns if they don't exist
        if '_features_processed' not in df.columns:
            df['_features_processed'] = False
        if '_description_processed' not in df.columns:
            df['_description_processed'] = False

        for i in range(start_row, len(df)):
            if not df.at[i, '_features_processed'] or not df.at[i, '_description_processed']:
                return i
        return -1

    def process_excel_file(self, input_file: str, output_file: str, start_row: int = 0, delay: float = 1.0):
        """
        Process the Excel file with resume capability.

        Args:
            input_file (str): Path to input Excel file
            output_file (str): Path to output Excel file
            start_row (int): Row index to start processing from (0-based)
            delay (float): Delay between API calls to avoid rate limits
        """
        # Load or create the working dataframe
        df = self.load_or_create_output_file(input_file, output_file)

        # Verify required columns exist
        required_columns = ['id', 'producer', 'productName', 'price', 'xkomCategory', 'features', 'productDescription']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            return

        print(f"Total rows in file: {len(df)}")

        # Find the actual starting point (first unprocessed row from start_row onwards)
        actual_start = self.find_next_unprocessed_row(df, start_row)

        if actual_start == -1:
            print("All rows have been processed!")
            return

        print(f"Starting processing from row {actual_start + 1} (index {actual_start})")

        # Process each row starting from the specified row
        for index in range(actual_start, len(df)):
            row = df.iloc[index]
            print(f"\nProcessing row {index + 1}/{len(df)} (ID: {row['id']})")

            # Check if features need processing
            if not df.at[index, '_features_processed']:
                print("  - Processing features...")
                try:
                    processed_features = self.process_features(str(row['features']))
                    df.at[index, 'features'] = processed_features
                    df.at[index, '_features_processed'] = True
                    print("  - Features processed successfully")

                    # Save progress after features
                    self.save_progress(df, output_file)
                    time.sleep(delay)
                except Exception as e:
                    print(f"  - Error processing features: {e}")
                    continue
            else:
                print("  - Features already processed, skipping")

            # Check if description needs processing
            if not df.at[index, '_description_processed']:
                print("  - Processing product description...")
                try:
                    processed_description = self.process_description(str(row['productDescription']))
                    df.at[index, 'productDescription'] = processed_description
                    df.at[index, '_description_processed'] = True
                    print("  - Description processed successfully")

                    # Save progress after description
                    self.save_progress(df, output_file)
                    time.sleep(delay)
                except Exception as e:
                    print(f"  - Error processing description: {e}")
                    continue
            else:
                print("  - Description already processed, skipping")

            print(f"  - Completed row {index + 1}")

        # Final save with clean data (remove tracking columns)
        print(f"\nAll processing completed! Final save to: {output_file}")
        self.save_progress(df, output_file)
        print("Processing completed successfully!")

    def get_processing_status(self, output_file: str):
        """
        Get current processing status of the file.

        Args:
            output_file (str): Path to output Excel file
        """
        if not os.path.exists(output_file):
            print(f"Output file {output_file} does not exist yet.")
            return

        try:
            df = pd.read_excel(output_file)
            total_rows = len(df)

            # Check if tracking columns exist
            if '_features_processed' in df.columns and '_description_processed' in df.columns:
                features_processed = df['_features_processed'].sum()
                descriptions_processed = df['_description_processed'].sum()
                fully_processed = (df['_features_processed'] & df['_description_processed']).sum()

                print(f"Processing Status for {output_file}:")
                print(f"Total rows: {total_rows}")
                print(f"Features processed: {features_processed}/{total_rows}")
                print(f"Descriptions processed: {descriptions_processed}/{total_rows}")
                print(f"Fully processed rows: {fully_processed}/{total_rows}")

                # Find next unprocessed row
                next_unprocessed = self.find_next_unprocessed_row(df, 0)
                if next_unprocessed != -1:
                    print(f"Next unprocessed row: {next_unprocessed + 1} (index {next_unprocessed})")
                else:
                    print("All rows have been processed!")
            else:
                print(f"File has {total_rows} rows, but no processing status available.")
                print("This appears to be a fresh file or completed processing.")

        except Exception as e:
            print(f"Error reading status: {e}")


def main():
    """
    Main function to run the Excel processor.
    """
    # Configuration
    API_KEY = "AIzaSyAZ_5ZrNP7-ReXst2jLISYDWdhRKYU3zQo"  # Replace with your actual API key
    INPUT_FILE = "products_data_1.xlsx"  # Replace with your input file path
    OUTPUT_FILE = "processed_products_data_2.xlsx"  # Replace with your desired output file path
    START_ROW = 0  # Row index to start from (0-based, so 0 = first row)
    DELAY_BETWEEN_CALLS = 4.0  # Delay in seconds between API calls

    # You can also get API key from environment variable
    # API_KEY = os.getenv('GEMINI_API_KEY')

    if API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("Please set your Gemini API key in the script or as an environment variable.")
        return

    # Initialize processor
    processor = ExcelGeminiProcessor(API_KEY)

    # Uncomment the line below to check processing status before starting
    # processor.get_processing_status(OUTPUT_FILE)

    # Process the file
    print(f"Starting processing from row {START_ROW + 1}...")
    processor.process_excel_file(INPUT_FILE, OUTPUT_FILE, START_ROW, DELAY_BETWEEN_CALLS)


if __name__ == "__main__":
    main()