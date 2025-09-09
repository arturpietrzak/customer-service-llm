import pandas as pd
import json
import time
from typing import List, Dict, Any
import os
from pathlib import Path
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

class AnswerGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-05-20",
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "response": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": ["response"]
                }
            )
        )
        
    def load_xlsx(self, file_path: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(file_path)
            print(f"Loaded {len(df)} rows from {file_path}")
            
            # Verify required columns exist
            required_columns = ['id', 'xkomCategory', 'producer', 'productName', 
                              'price', 'features', 'productDescription', 'questions']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
                
            return df
            
        except Exception as e:
            print(f"Error loading XLSX file: {e}")
            raise
    
    def create_prompt(self, features: str, product_description: str, questions: str) -> str:
        prompt = f"""Na podstawie dostarczonej specyfikacji technicznej i opisu marketingowego produktu (smartfona), odpowiedz szczegółowo na poniższe 15 pytań.
Jeśli pytanie zawiera kilka części (np. dotyczy więcej niż jednego parametru lub aspektu), odpowiedz na każdą część osobno, w punktach lub odrębnych akapitach.
Jeśli w dostępnych materiałach brakuje informacji potrzebnych do odpowiedzi na jakąkolwiek część pytania, wyraźnie zaznacz to, pisząc: "Brak danych w dostępnej specyfikacji i opisie marketingowym."
Odpowiedzi powinny być konkretne, zwięzłe i oparte wyłącznie na dostarczonych danych, bez zgadywania.
Nie dodawaj własnych założeń ani informacji spoza źródeł.
Nie dodawaj numerów pytań przed odpowiedziami.

Pytania:
{questions}

Specyfikacja:
{features}

Opis:
{product_description}"""
        
        return prompt
    
    def call_gemini_api(self, prompt: str, max_retries: int = 3) -> List[str]:
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                parsed_response = json.loads(response.text)
                
                if 'response' in parsed_response and isinstance(parsed_response['response'], list):
                    responses = parsed_response['response']
                    
                    # In case of error make all lengths 15 
                    if len(responses) < 15:
                        responses.extend([''] * (15 - len(responses)))
                    elif len(responses) > 15:
                        responses = responses[:15]
                        
                    return responses
                else:
                    raise ValueError("Invalid response format from API")
                    
            except genai.types.BlockedPromptException as e:
                print(f"Prompt was blocked: {e}")
                return ['Prompt blocked by safety filters'] * 15
                
            except genai.types.StopCandidateException as e:
                print(f"Generation stopped: {e}")
                return ['Generation stopped by safety filters'] * 15
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
            except Exception as e:
                print(f"Error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        # If all retries failed, return empty responses
        print("All retries failed")
        return [''] * 15
    
    def process_dataframe(self, df: pd.DataFrame, delay_seconds: float = 1.0) -> pd.DataFrame:
        result_df = df.copy()
        for i in range(1, 16):
            result_df[f'r{i}'] = ''
        
        print(f"Processing {len(df)} rows...")
        
        for index, row in df.iterrows():
            print(f"Processing row {index + 1}/{len(df)} (ID: {row['id']})")
            
            features = str(row['features']) if pd.notna(row['features']) else ''
            product_description = str(row['productDescription']) if pd.notna(row['productDescription']) else ''
            questions = str(row['questions']) if pd.notna(row['questions']) else ''
            
            if not features and not product_description and not questions:
                print(f"Skipping row {index + 1} - all required fields are empty")
                continue
            
            prompt = self.create_prompt(features, product_description, questions)
            responses = self.call_gemini_api(prompt)
            for i, response in enumerate(responses, 1):
                result_df.at[index, f'r{i}'] = response
            
            if index < len(df) - 1: 
                time.sleep(delay_seconds)
        
        print("Processing completed!")
        return result_df
    
    def save_xlsx(self, df: pd.DataFrame, output_path: str):
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            df.to_excel(output_path, index=False)
            print(f"Results saved to {output_path}")
        except Exception as e:
            print(f"Error saving XLSX file: {e}")
            raise
    
    def process_file(self, input_file: str, output_file: str, delay_seconds: float = 1.0):
        try:
            df = self.load_xlsx(input_file)
            processed_df = self.process_dataframe(df, delay_seconds)
            self.save_xlsx(processed_df, output_file)
            
            print(f"\nProcessing complete!")
            print(f"Input: {input_file}")
            print(f"Output: {output_file}")
            print(f"Processed {len(df)} products")
            
        except Exception as e:
            print(f"Error in processing pipeline: {e}")
            raise
    
def main():
    API_KEY = ""
    INPUT_FILE = "processed_products_data_clean_test.xlsx"
    OUTPUT_FILE = "output_products_2.xlsx"
    DELAY_SECONDS = 3.0

    # Check if input file exists
    if not os.path.exists(INPUT_FILE):
        print(f"Input file '{INPUT_FILE}' not found. Please check the file path.")
        return
    
    try:
        # Create processor instance
        processor = AnswerGenerator(API_KEY)
        
        # Choose processing method:
        # Option 1: Process all at once
        processor.process_file(INPUT_FILE, OUTPUT_FILE, DELAY_SECONDS)
        
        # Option 2: Process in batches (uncomment to use)
        # processor.process_batch(INPUT_FILE, OUTPUT_FILE, BATCH_SIZE, DELAY_SECONDS)
        
    except Exception as e:
        print(f"Application error: {e}")


if __name__ == "__main__":
    main()