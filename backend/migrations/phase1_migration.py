#!/usr/bin/env python3
"""
Phase 1 Database Migration

Creates the x402_calls table for payment verification tracking.
This follows the backward compatibility rule - only adds new columns/tables.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.pocketbase import pb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

class Phase1Migration:
    """Phase 1 database migration"""
    
    def __init__(self):
        self.migrations_completed = []
    
    async def create_x402_calls_table(self):
        """Create x402_calls table for payment verification"""
        logger.info("Creating x402_calls table...")
        
        try:
            # Check if table already exists
            try:
                existing = await pb.collection('x402_calls').get_first_item()
                logger.info("x402_calls table already exists")
                self.migrations_completed.append("x402_calls_table_exists")
                return True
            except:
                pass  # Table doesn't exist, create it
            
            # Create the collection
            collection_data = {
                "name": "x402_calls",
                "type": "base",
                "schema": [
                    {
                        "name": "id",
                        "type": "text",
                        "required": True,
                        "options": {
                            "min": 1,
                            "max": 100
                        }
                    },
                    {
                        "name": "task_id",
                        "type": "text",
                        "required": True,
                        "options": {
                            "min": 1,
                            "max": 100
                        }
                    },
                    {
                        "name": "agent_id",
                        "type": "text",
                        "required": True,
                        "options": {
                            "min": 1,
                            "max": 100
                        }
                    },
                    {
                        "name": "service_name",
                        "type": "text",
                        "required": False,
                        "options": {
                            "min": 1,
                            "max": 50
                        }
                    },
                    {
                        "name": "request_hash",
                        "type": "text",
                        "required": False,
                        "options": {
                            "min": 1,
                            "max": 100
                        }
                    },
                    {
                        "name": "amount_sol",
                        "type": "number",
                        "required": True,
                        "options": {
                            "min": 0,
                            "max": 1000000
                        }
                    },
                    {
                        "name": "solscan_tx",
                        "type": "text",
                        "required": True,
                        "options": {
                            "min": 1,
                            "max": 100
                        }
                    },
                    {
                        "name": "status",
                        "type": "select",
                        "required": True,
                        "options": {
                            "values": ["pending", "confirmed", "failed", "not_found", "invalid"]
                        }
                    },
                    {
                        "name": "verified_at",
                        "type": "number",
                        "required": False,
                        "options": {
                            "min": 0
                        }
                    },
                    {
                        "name": "created_at",
                        "type": "number",
                        "required": True,
                        "options": {
                            "min": 0
                        }
                    }
                ],
                "indexes": [
                    "CREATE UNIQUE INDEX idx_x402_calls_id ON x402_calls (id)",
                    "CREATE INDEX idx_x402_calls_task_id ON x402_calls (task_id)",
                    "CREATE INDEX idx_x402_calls_agent_id ON x402_calls (agent_id)",
                    "CREATE INDEX idx_x402_calls_status ON x402_calls (status)",
                    "CREATE INDEX idx_x402_calls_solscan_tx ON x402_calls (solscan_tx)"
                ]
            }
            
            # Create collection via API
            await pb.collections.create(collection_data)
            
            logger.info("x402_calls table created successfully")
            self.migrations_completed.append("x402_calls_table_created")
            return True
            
        except Exception as error:
            logger.error(f"Failed to create x402_calls table: {error}")
            return False
    
    async def verify_migration(self):
        """Verify migration was successful"""
        logger.info("Verifying migration...")
        
        try:
            # Test table access
            test_record = {
                "id": "migration_test",
                "task_id": "test_task",
                "agent_id": "test_agent",
                "amount_sol": 0.001,
                "solscan_tx": "test_tx_hash",
                "status": "pending",
                "created_at": 1234567890
            }
            
            # Create test record
            created = await pb.collection('x402_calls').create(test_record)
            
            # Read test record
            retrieved = await pb.collection('x402_calls').get(created.id)
            
            # Clean up test record
            await pb.collection('x402_calls').delete(created.id)
            
            if retrieved.id == created.id:
                logger.info("Migration verification successful")
                self.migrations_completed.append("migration_verified")
                return True
            else:
                logger.error("Migration verification failed - record mismatch")
                return False
                
        except Exception as error:
            logger.error(f"Migration verification failed: {error}")
            return False
    
    async def run_migration(self):
        """Run all Phase 1 migrations"""
        logger.info("Starting Phase 1 Database Migration...")
        
        migrations = [
            self.create_x402_calls_table,
            self.verify_migration
        ]
        
        for migration in migrations:
            try:
                result = await migration()
                if not result:
                    logger.error(f"Migration {migration.__name__} failed")
                    return False
            except Exception as error:
                logger.error(f"Migration {migration.__name__} crashed: {error}")
                return False
        
        # Print results
        logger.info("\n=== PHASE 1 MIGRATION RESULTS ===")
        for migration in self.migrations_completed:
            logger.info(f"Completed: {migration}")
        
        logger.info(f"\nSummary: {len(self.migrations_completed)} migrations completed")
        
        if len(self.migrations_completed) >= 2:
            logger.info("Phase 1 migration completed successfully!")
            return True
        else:
            logger.error("Phase 1 migration incomplete.")
            return False

async def main():
    """Main migration runner"""
    # Check PocketBase connection
    try:
        await pb.health_check()
        logger.info("PocketBase connection verified")
    except Exception as error:
        logger.error(f"PocketBase connection failed: {error}")
        logger.error("Make sure PocketBase is running")
        sys.exit(1)
    
    migrator = Phase1Migration()
    success = await migrator.run_migration()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
