#!/usr/bin/env python3

import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util.alerts import send_ntfy_alerts

def test_ntfy_integration():
    """Test the ntfy integration with current .env values"""
    
    # Print current environment variables
    logger.info("=== NTFY Configuration from .env ===")
    logger.info(f"NTFY_URL: {os.getenv('NTFY_URL', 'Not set')}")
    logger.info(f"NTFY_TOPIC: {os.getenv('NTFY_TOPIC', 'Not set')}")
    logger.info(f"NTFY_USER: {os.getenv('NTFY_USER', 'Not set')}")
    logger.info(f"NTFY_PASSWORD: {os.getenv('NTFY_PASSWORD', 'Not set')}")
    logger.info(f"NTFY_TOKEN: {repr(os.getenv('NTFY_TOKEN', 'Not set'))}")
    
    # Check if NTFY_TOKEN is actually set
    token = os.getenv('NTFY_TOKEN')
    if token:
        logger.info("✅ NTFY_TOKEN is set correctly")
    else:
        logger.warning("⚠️  NTFY_TOKEN appears to be empty or not set properly")
    
    # Test with a simple alert
    test_alerts = ["Test alert from AI-Monitor", "This is a sample alert for testing ntfy integration"]
    
    logger.info("=== Testing ntfy Alert Integration ===")
    logger.info(f"Sending alerts: {test_alerts}")
    
    success = send_ntfy_alerts(test_alerts)
    
    if success:
        logger.info("✅ Successfully sent test alerts to ntfy")
        return True
    else:
        logger.error("❌ Failed to send test alerts to ntfy")
        return False

if __name__ == "__main__":
    test_ntfy_integration()