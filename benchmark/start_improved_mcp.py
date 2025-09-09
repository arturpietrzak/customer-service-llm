#!/usr/bin/env python3

import sys
import os
import uvicorn
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    host = os.getenv("MCP_SERVER_HOST", "localhost")
    port = int(os.getenv("MCP_SERVER_PORT", "8001"))
    
    print("🚀 Starting LLM-Friendly Product Search MCP Server")
    print("=" * 55)
    print(f"🌐 Server URL: http://{host}:{port}")
    print(f"📖 API Documentation: http://{host}:{port}/docs")
    print(f"🤖 LLM Instructions: http://{host}:{port}/llm_instructions")
    print(f"🔍 Main Search Endpoint: POST http://{host}:{port}/search_products")
    print()
    print("🎯 Quick Test Examples:")
    print("  • Find iPhones: curl -X POST 'http://localhost:8001/search_products' -H 'Content-Type: application/json' -d '{\"name\": \"iPhone\"}'")
    print("  • Find cheap keyboards: curl -X POST 'http://localhost:8001/search_products' -H 'Content-Type: application/json' -d '{\"category\": \"Klawiatury\", \"max_price\": 200, \"sort_by\": \"price_asc\"}'")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 55)
    
    try:
        uvicorn.run(
            "src.mcp.improved_server:app", 
            host=host, 
            port=port,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()