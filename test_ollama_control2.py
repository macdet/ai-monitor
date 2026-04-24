#!/usr/bin/env python3
"""
Test script for ollama_control2.py functions
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util.ollama_control2 import (
    get_loaded_ollama_models,
    unload_ollama_model,
    unload_current_ollama_model,
)


def test_get_loaded_ollama_models():
    """Test getting loaded ollama models"""
    print("Testing get_loaded_ollama_models...")
    try:
        models = get_loaded_ollama_models()
        print(f"Found {len(models)} loaded models:")
        for model in models:
            print(f"  - {model}")
        return True
    except Exception as e:
        print(f"Error getting loaded models: {e}")
        return False


def test_unload_ollama_model():
    """Test unloading a specific model (if any models are loaded)"""
    print("\nTesting unload_ollama_model...")
    try:
        models = get_loaded_ollama_models()
        if models:
            model_to_unload = models[0]
            print(f"Attempting to unload: {model_to_unload}")
            result = unload_ollama_model(model_to_unload)
            print(f"Unload result: {result}")
            return True
        else:
            print("No models currently loaded to test unloading")
            return True
    except Exception as e:
        print(f"Error unloading model: {e}")
        return False


def test_unload_current_ollama_model():
    """Test unloading the current model"""
    print("\nTesting unload_current_ollama_model...")
    try:
        result, model = unload_current_ollama_model()
        print(f"Unload result: {result}, Model: {model}")
        return True
    except Exception as e:
        print(f"Error unloading current model: {e}")
        return False


if __name__ == "__main__":
    print("Running Ollama Control2 Tests")
    print("=" * 40)

    success = True
    success &= test_get_loaded_ollama_models()
    success &= test_unload_ollama_model()
    success &= test_unload_current_ollama_model()

    print("\n" + "=" * 40)
    if success:
        print("All tests completed successfully")
    else:
        print("Some tests failed")
        sys.exit(1)
