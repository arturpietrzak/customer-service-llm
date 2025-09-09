from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import logging
import os
from ..database.connection import DatabaseConnection
from ..database.models import Product

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM-Friendly Product Search API",
    description="Simple and powerful product database search optimized for LLM interactions",
    version="1.0.0"
)

db_connection = None

def get_db() -> DatabaseConnection:
    global db_connection
    if db_connection is None:
        db_path = os.getenv("DATABASE_PATH", "data/products.db")
        db_connection = DatabaseConnection(db_path)
    return db_connection

class ProductSearchRequest(BaseModel):
    name: Optional[str] = Field(None, description="Search in product name, description, and features")
    category: Optional[str] = Field(None, description="Filter by category (e.g., 'Laptopy', 'Klawiatury', 'Smartfony')")
    producer: Optional[str] = Field(None, description="Filter by producer/brand (e.g., 'ASUS', 'Apple', 'Logitech')")
    min_price: Optional[float] = Field(None, description="Minimum price in PLN")
    max_price: Optional[float] = Field(None, description="Maximum price in PLN")
    sort_by: Literal["price_asc", "price_desc", "name", "relevance"] = Field("relevance", description="Sort results by price (ascending/descending), name, or relevance")
    limit: int = Field(10, description="Maximum number of products to return (1-50)")

class ProductSearchResponse(BaseModel):
    products: List[Product]
    total_found: int
    search_info: dict
    available_categories: List[str]
    available_producers: List[str]
    price_range: dict

@app.get("/")
async def root():
    return {
        "name": "LLM-Friendly Product Search API",
        "version": "1.0.0",
        "description": "Search products by name, category, producer, and price with sorting options",
        "main_endpoint": "/search_products",
        "documentation": "/docs",
        "quick_examples": {
            "find_phones": '{"name": "iPhone"}',
            "find_cheap_keyboards": '{"category": "Klawiatury", "max_price": 200, "sort_by": "price_asc"}',
            "find_gaming_gear": '{"name": "gaming", "limit": 5}',
            "find_asus_products": '{"producer": "ASUS", "sort_by": "price_desc"}'
        }
    }

@app.post("/search_products", response_model=ProductSearchResponse)
async def search_products(request: ProductSearchRequest, db: DatabaseConnection = Depends(get_db)):
    try:
        if request.limit > 50:
            request.limit = 50
        elif request.limit < 1:
            request.limit = 1
        
        search_params = {
            "query": request.name or "",
            "category": request.category,
            "producer": request.producer, 
            "min_price": request.min_price,
            "max_price": request.max_price,
            "limit": request.limit
        }
        
        products_data = db.search_products(**search_params)
        
        if request.sort_by == "price_asc":
            products_data.sort(key=lambda x: x.get('price', 0))
        elif request.sort_by == "price_desc":
            products_data.sort(key=lambda x: x.get('price', 0), reverse=True)
        elif request.sort_by == "name":
            products_data.sort(key=lambda x: x.get('product_name', '').lower())
        
        products = [Product(**data) for data in products_data]
        
        all_categories = db.get_categories()
        all_producers = db.get_producers()
        
        prices = [p.price for p in products if p.price]
        price_range = {
            "min": min(prices) if prices else 0,
            "max": max(prices) if prices else 0,
            "average": sum(prices) / len(prices) if prices else 0
        }
        
        return ProductSearchResponse(
            products=products,
            total_found=len(products),
            search_info={
                "search_term": request.name,
                "category_filter": request.category,
                "producer_filter": request.producer,
                "price_range_filter": f"{request.min_price or 0}-{request.max_price or '∞'} PLN",
                "sorted_by": request.sort_by,
                "limit": request.limit
            },
            available_categories=all_categories[:20],
            available_producers=all_producers[:30]
            price_range=price_range
        )
        
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/categories")
async def get_all_categories(db: DatabaseConnection = Depends(get_db)):
    try:
        categories = db.get_categories()
        return {
            "categories": categories,
            "count": len(categories),
            "usage_tip": "Use these exact names in the 'category' field when searching"
        }
    except Exception as e:
        logger.error(f"Get categories failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@app.get("/producers")
async def get_all_producers(db: DatabaseConnection = Depends(get_db)):
    try:
        producers = db.get_producers()
        return {
            "producers": producers,
            "count": len(producers),
            "usage_tip": "Use these exact names in the 'producer' field when searching"
        }
    except Exception as e:
        logger.error(f"Get producers failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get producers: {str(e)}")

@app.get("/stats")
async def get_database_stats(db: DatabaseConnection = Depends(get_db)):
    try:
        stats = db.get_stats()
        return {
            **stats,
            "api_info": {
                "max_results_per_search": 50,
                "default_limit": 10,
                "supported_sorting": ["price_asc", "price_desc", "name", "relevance"],
                "currency": "PLN"
            }
        }
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/health")
async def health_check(db: DatabaseConnection = Depends(get_db)):
    try:
        stats = db.get_stats()
        return {
            "status": "healthy",
            "database": {
                "connected": True,
                "products": stats.get("total_products", 0),
                "categories": stats.get("total_categories", 0),
                "producers": stats.get("total_producers", 0)
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")

@app.get("/llm_instructions")
async def get_llm_instructions():
    return {
        "tool_name": "search_products",
        "endpoint": "POST /search_products", 
        "purpose": "Find products with flexible search and filtering",
        "max_results": 50,
        "default_limit": 10,
        "currency": "PLN",
        "sort_options": ["price_asc", "price_desc", "name", "relevance"],
        "required_fields": [],
        "optional_fields": ["name", "category", "producer", "min_price", "max_price", "sort_by", "limit"],
        "response_includes": [
            "Complete product details (name, description, features, price)",
            "Available categories and producers for context",
            "Search metadata and price statistics"
        ],
        "common_use_cases": [
            "Find products by name or description",
            "Filter by category (Laptopy, Smartfony, etc.)",
            "Filter by brand/producer (ASUS, Apple, etc.)",
            "Find products in price range",
            "Sort by price (cheapest/most expensive first)"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(level=logging.INFO)
    
    host = os.getenv("MCP_SERVER_HOST", "localhost")
    port = int(os.getenv("MCP_SERVER_PORT", "8001"))
    
    logger.info(f"Starting improved LLM-friendly MCP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)