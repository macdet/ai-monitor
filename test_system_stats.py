#!/usr/bin/env python3
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Manually test just the core functionality
try:
    import psutil
    print("psutil imported successfully")
    
    # Simple test function
    def test_basic():
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        print(f"CPU: {cpu}%")
        print(f"Memory: {memory.percent}%")
        print(f"Disk: {(disk.used / disk.total) * 100:.2f}%")
        return True
    
    test_basic()
    print("System stats test completed successfully")
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Try installing psutil: pip install psutil")
except Exception as e:
    print(f"Error: {e}")