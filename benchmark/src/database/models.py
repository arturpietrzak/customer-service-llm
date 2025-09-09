from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    id: int = Field(..., description="Unique product identifier")
    xkom_category: str = Field(..., description="Product category from x-kom")
    producer: str = Field(..., description="Product manufacturer")
    product_name: str = Field(..., description="Product name")
    price: float = Field(..., description="Product price")
    features: str = Field(..., description="Product features as text")
    product_description: str = Field(..., description="Product description")
    
    class Config:
        from_attributes = True


class ProductQuery(BaseModel):
    query: str = Field(..., description="Search query for products")
    category: Optional[str] = Field(None, description="Filter by category")
    producer: Optional[str] = Field(None, description="Filter by producer")
    min_price: Optional[Union[float, str]] = Field(None, description="Minimum price filter")
    max_price: Optional[Union[float, str]] = Field(None, description="Maximum price filter")
    limit: Optional[Union[int, str]] = Field(10, description="Maximum number of results")
    
    @field_validator('min_price', mode='before')
    @classmethod
    def convert_min_price(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v
    
    @field_validator('max_price', mode='before')
    @classmethod
    def convert_max_price(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v
    
    @field_validator('limit', mode='before')
    @classmethod
    def convert_limit(cls, v):
        if v is None or v == "":
            return 10
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 10 
        return v


class ProductSearchResult(BaseModel):
    products: list[Product]
    total_count: int
    query_info: ProductQuery