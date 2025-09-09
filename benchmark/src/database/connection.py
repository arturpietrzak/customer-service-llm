import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self, db_path: str = "data/products.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    xkom_category TEXT NOT NULL,
                    producer TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    features TEXT NOT NULL,
                    product_description TEXT NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(xkom_category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_producer ON products(producer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price ON products(price)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_name_fts ON products(product_name)")
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_products(self, products: List[Dict[str, Any]]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO products 
                (id, xkom_category, producer, product_name, price, features, product_description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (p['id'], p['xkom_category'], p['producer'], p['product_name'], 
                 p['price'], p['features'], p['product_description'])
                for p in products
            ])
            conn.commit()
            return cursor.rowcount
    
    def search_products(
        self, 
        query: str = "", 
        category: Optional[str] = None,
        producer: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            sql_parts = ["SELECT * FROM products WHERE 1=1"]
            params = []
            
            if query:
                sql_parts.append("AND (product_name LIKE ? OR product_description LIKE ? OR features LIKE ?)")
                query_param = f"%{query}%"
                params.extend([query_param, query_param, query_param])
            
            if category:
                sql_parts.append("AND xkom_category LIKE ?")
                params.append(f"%{category}%")
            
            if producer:
                sql_parts.append("AND producer LIKE ?")
                params.append(f"%{producer}%")
            
            if min_price is not None:
                sql_parts.append("AND price >= ?")
                params.append(min_price)
            
            if max_price is not None:
                sql_parts.append("AND price <= ?")
                params.append(max_price)
            
            sql_parts.append("LIMIT ?")
            params.append(limit)
            
            sql = " ".join(sql_parts)
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_categories(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT xkom_category FROM products ORDER BY xkom_category")
            return [row[0] for row in cursor.fetchall()]
    
    def get_producers(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT producer FROM products ORDER BY producer")
            return [row[0] for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_products,
                    COUNT(DISTINCT xkom_category) as total_categories,
                    COUNT(DISTINCT producer) as total_producers,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price) as avg_price
                FROM products
            """)
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def clear_products(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM products")
            conn.commit()
            return cursor.rowcount