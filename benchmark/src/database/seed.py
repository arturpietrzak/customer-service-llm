import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Any, List
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


class DatabaseSeeder:
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
    
    def load_excel_data(self, excel_path: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(excel_path)
            logger.info(f"Loaded {len(df)} rows from {excel_path}")
            return df
        except Exception as e:
            logger.error(f"Failed to load Excel file {excel_path}: {e}")
            raise
    
    def validate_and_clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        required_cols = ['id', 'xkomCategory', 'producer', 'productName', 'price', 'features', 'productDescription']
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        df = df.rename(columns={
            'xkomCategory': 'xkom_category',
            'productName': 'product_name',
            'productDescription': 'product_description'
        })
        
        df = df[['id', 'xkom_category', 'producer', 'product_name', 'price', 'features', 'product_description']]
        
        df = df.dropna(subset=['id', 'product_name'])
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df = df.dropna(subset=['price'])
        
        text_columns = ['xkom_category', 'producer', 'features', 'product_description']
        for col in text_columns:
            df[col] = df[col].fillna('')
        
        df = df.drop_duplicates(subset=['id'])
        
        df['id'] = df['id'].astype(int)
        
        logger.info(f"After cleaning: {len(df)} valid products")
        return df
    
    def seed_database(self, excel_path: str, clear_existing: bool = True) -> Dict[str, Any]:
        logger.info(f"Starting database seeding from {excel_path}")
        
        df = self.load_excel_data(excel_path)
        df = self.validate_and_clean_data(df)
        
        if clear_existing:
            cleared_count = self.db.clear_products()
            logger.info(f"Cleared {cleared_count} existing products")
        
        products = df.to_dict('records')
        
        inserted_count = self.db.insert_products(products)
        
        stats = self.db.get_stats()
        
        result = {
            'inserted_count': inserted_count,
            'total_products': stats.get('total_products', 0),
            'categories': stats.get('total_categories', 0),
            'producers': stats.get('total_producers', 0),
            'price_range': {
                'min': stats.get('min_price', 0),
                'max': stats.get('max_price', 0),
                'avg': stats.get('avg_price', 0)
            }
        }
        
        logger.info(f"Database seeding completed: {result}")
        return result
    
    def validate_seeded_data(self) -> bool:
        stats = self.db.get_stats()
        categories = self.db.get_categories()
        producers = self.db.get_producers()
        
        if stats.get('total_products', 0) == 0:
            logger.error("No products found in database")
            return False
        
        if stats.get('total_categories', 0) == 0:
            logger.error("No categories found in database")
            return False
        
        if stats.get('min_price', 0) < 0:
            logger.error("Invalid negative prices found")
            return False
        
        logger.info(f"Database validation passed:")
        logger.info(f"  - Total products: {stats['total_products']}")
        logger.info(f"  - Categories: {stats['total_categories']}")
        logger.info(f"  - Producers: {stats['total_producers']}")
        logger.info(f"  - Price range: {stats['min_price']:.2f} - {stats['max_price']:.2f}")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed the products database")
    parser.add_argument("excel_path", help="Path to the Excel file with product data")
    parser.add_argument("--db-path", default="data/products.db", help="Database path")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing data")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    db = DatabaseConnection(args.db_path)
    seeder = DatabaseSeeder(db)
    
    try:
        result = seeder.seed_database(args.excel_path, clear_existing=not args.no_clear)
        
        if seeder.validate_seeded_data():
            print("Database seeding completed successfully!")
            print(f"Inserted {result['inserted_count']} products")
        else:
            print("Database validation failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())