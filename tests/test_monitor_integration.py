import pytest
from unittest.mock import MagicMock, patch
from monitor import build_snapshot, print_snapshot, append_snapshot
import json
from pathlib import Path

def test_build_snapshot():
    """Test: build_snapshot funktioniert korrekt"""
    snapshot = build_snapshot()
    assert isinstance(snapshot, dict)
    assert "timestamp" in snapshot
    assert "gpu_temp" in snapshot
    assert "ollama_models" in snapshot
    assert "state" in snapshot

def test_print_snapshot():
    """Test: print_snapshot funktioniert korrekt"""
    snapshot = build_snapshot()
    # Should not raise an exception
    print_snapshot(snapshot)

def test_append_snapshot():
    """Test: append_snapshot funktioniert korrekt"""
    snapshot = build_snapshot()
    append_snapshot(snapshot)
    
    # Verify the history file was created and has content
    history_file = Path("history/monitor_history.jsonl")
    assert history_file.exists()
    
    # Read back the content to verify it's valid JSON
    with open(history_file, 'r') as f:
        line = f.readline()
        assert line.strip() != ""
        
        # Try to parse the JSON
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

def test_monitor_integration():
    """Integrationtest für den Monitor"""
    # Test that we can build a snapshot
    snapshot = build_snapshot()
    assert isinstance(snapshot, dict)
    
    # Test that we can print a snapshot (should not raise an exception)
    print_snapshot(snapshot)
    
    # Test that we can append a snapshot to the history file
    append_snapshot(snapshot)
    
    # Verify the history file was created and has content
    history_file = Path("history/monitor_history.jsonl")
    assert history_file.exists()
    
    # Read back the content to verify it's valid JSON
    with open(history_file, 'r') as f:
        line = f.readline()
        assert line.strip() != ""
        
        # Try to parse the JSON
        parsed = json.loads(line)
        assert isinstance(parsed, dict)
