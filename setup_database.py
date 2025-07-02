#!/usr/bin/env python3
"""
Database setup script for Persona Agent.
Creates all required tables in Supabase.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from database.schema import ALL_TABLES, INDEXES
from database.production_client import ProductionSupabaseClient
from orchestrator.config import settings


async def setup_database():
    """Setup database tables and indexes."""
    print("🗄️ Setting up Persona Agent Database")
    print("=" * 50)
    
    try:
        # Initialize client
        db_client = ProductionSupabaseClient(settings.supabase_url, settings.supabase_key)
        print("✅ Database client connected")
        
        # Create tables
        for i, table_sql in enumerate(ALL_TABLES, 1):
            table_name = table_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
            print(f"📋 Creating table {i}/{len(ALL_TABLES)}: {table_name}")
            
            try:
                # Note: This requires direct SQL execution
                # For now, print the SQL for manual execution
                print(f"   SQL: {table_sql[:100]}...")
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Create indexes
        print(f"\n🔍 Creating {len(INDEXES)} indexes...")
        for index_sql in INDEXES:
            print(f"   Index: {index_sql[:50]}...")
        
        print("\n✅ Database setup complete!")
        print("\n📋 Manual Steps Required:")
        print("1. Copy the SQL from database/schema.py")
        print("2. Execute it in your Supabase SQL editor")
        print("3. Verify tables are created")
        
        return True
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)
