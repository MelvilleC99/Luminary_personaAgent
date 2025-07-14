"""Supabase configuration and connection setup"""

from datetime import timedelta
from orchestrator.config import settings
from data.supabase.supabase_utils import supabase_manager


async def initialize_supabase():
    """Initialize Supabase connection and verify connectivity"""
    try:
        # Check if Supabase credentials are provided
        if not settings.supabase_url or not settings.supabase_key:
            print("⚠️ Supabase credentials not provided. Supabase features will be disabled.")
            return True  # Return True to allow the app to start without Supabase
        
        # Initialize the Supabase client first
        supabase_manager._initialize_connection()
        
        # Test connection by attempting a simple query
        stats = await supabase_manager.get_completion_stats(days=1)
        if "error" not in stats:
            print(f"✅ Supabase connected successfully")
            return True
        else:
            print(f"❌ Supabase connection failed: {stats['error']}")
            return False
    except Exception as e:
        print(f"❌ Supabase initialization failed: {e}")
        return False


async def verify_schema():
    """Verify that required tables exist"""
    try:
        # Test each main table
        tables_to_check = ["personas", "conversation_logs", "session_analytics"]
        
        for table in tables_to_check:
            result = supabase_manager.client.table(table).select("id").limit(1).execute()
            # If we get here without exception, table exists
        
        print("✅ Supabase schema verified")
        return True
        
    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        print("Please ensure the database schema is created according to models.py")
        return False


# Export main components
__all__ = [
    "supabase_manager",
    "initialize_supabase",
    "verify_schema"
]
