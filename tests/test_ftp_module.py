"""Test script for FTP Module."""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.ftp_module import FTPModule
from app.models import PS5System
from config import settings


async def test_ftp_connection():
    """Test FTP connection to PS5."""
    # Create test PS5 system
    system = PS5System(
        name="Test PS5",
        ip_address="192.168.8.50",  # User's PS5 IP
        ftp_port=21,
        ftp_username="ftp",
        ftp_password="ftp",
    )
    
    # Create module
    module = FTPModule()
    await module.initialize()
    
    print("Testing FTP connection to PS5 at 192.168.8.50...")
    
    # Try to connect
    result = module.connect(system)
    print(f"Connection result: {result}")
    
    if result.get("success"):
        print("Connection successful!")
        
        # Test directory listing
        print("\nListing /data/app...")
        files = module.list_directory("/data/app")
        for f in files[:10]:
            print(f"  {f['name']} ({'dir' if f['is_dir'] else 'file'})")
        
        # Test scanning
        print("\nScanning for games...")
        scan_result = module.scan(system)
        print(f"Scan result: {scan_result}")
        
        module.disconnect()
    else:
        print(f"Connection failed: {result.get('error')}")
    
    await module.shutdown()


if __name__ == "__main__":
    asyncio.run(test_ftp_connection())