import time
from pathlib import Path
from unittest.mock import Mock

from frequencyman.lib.event_logger import EventLogger


def test_event_logger_initialization():
    """Test that EventLogger initializes with correct default values."""
    logger = EventLogger()
    
    assert logger.event_log == []
    assert logger.event_log_listeners == []
    assert logger.timed_entries_open == 0
    assert logger.time_started is None


def test_add_entry_basic():
    """Test adding a basic entry to the event log."""
    logger = EventLogger()
    
    index = logger.add_entry("Test message")
    
    assert index == 0
    assert logger.event_log == ["Test message"]
    assert logger.time_started is not None


def test_add_entry_multiple():
    """Test adding multiple entries to the event log."""
    logger = EventLogger()
    
    index1 = logger.add_entry("First message")
    index2 = logger.add_entry("Second message")
    index3 = logger.add_entry("Third message")
    
    assert index1 == 0
    assert index2 == 1
    assert index3 == 2
    assert logger.event_log == ["First message", "Second message", "Third message"]


def test_add_entry_starts_timer():
    """Test that adding the first entry starts the timer."""
    logger = EventLogger()
    
    assert logger.time_started is None
    logger.add_entry("First message")
    assert logger.time_started is not None


def test_add_entry_with_indentation():
    """Test that entries are indented when timed_entries_open > 0."""
    logger = EventLogger()
    
    logger.add_entry("Outer message")
    logger.timed_entries_open = 1
    logger.add_entry("Inner message")
    logger.timed_entries_open = 2
    logger.add_entry("Deeply nested message")
    
    assert logger.event_log[0] == "Outer message"
    assert logger.event_log[1] == "   Inner message"
    assert logger.event_log[2] == "     Deeply nested message"


def test_add_event_log_listener():
    """Test adding event log listeners."""
    logger = EventLogger()
    listener1 = Mock()
    listener2 = Mock()
    
    logger.add_event_log_listener(listener1)
    logger.add_event_log_listener(listener2)
    
    assert len(logger.event_log_listeners) == 2
    assert listener1 in logger.event_log_listeners
    assert listener2 in logger.event_log_listeners


def test_listener_called_on_add_entry():
    """Test that listeners are called when entries are added."""
    logger = EventLogger()
    listener = Mock()
    
    logger.add_event_log_listener(listener)
    logger.add_entry("Test message")
    
    listener.assert_called_once_with("Test message")


def test_multiple_listeners_called():
    """Test that all listeners are called when entries are added."""
    logger = EventLogger()
    listener1 = Mock()
    listener2 = Mock()
    listener3 = Mock()
    
    logger.add_event_log_listener(listener1)
    logger.add_event_log_listener(listener2)
    logger.add_event_log_listener(listener3)
    
    logger.add_entry("Test message")
    
    listener1.assert_called_once_with("Test message")
    listener2.assert_called_once_with("Test message")
    listener3.assert_called_once_with("Test message")


def test_get_elapsed_time_before_start():
    """Test that elapsed time is 0.0 before any entries are added."""
    logger = EventLogger()
    
    assert logger.get_elapsed_time() == 0.0


def test_get_elapsed_time_after_start():
    """Test that elapsed time increases after entries are added."""
    logger = EventLogger()
    
    logger.add_entry("Start")
    time.sleep(0.01)  # Sleep for 10ms
    elapsed = logger.get_elapsed_time()
    
    assert elapsed > 0.0
    assert elapsed >= 0.01


def test_add_benchmarked_entry_basic():
    """Test basic benchmarked entry functionality."""
    logger = EventLogger()
    
    with logger.add_benchmarked_entry("Benchmarked operation"):
        time.sleep(0.01)  # Sleep for 10ms
    
    assert len(logger.event_log) == 1
    assert "Benchmarked operation" in logger.event_log[0]
    assert "(took" in logger.event_log[0]


def test_add_benchmarked_entry_increments_timed_entries():
    """Test that timed_entries_open is incremented during benchmarked entry."""
    logger = EventLogger()
    assert logger.timed_entries_open == 0
    
    with logger.add_benchmarked_entry("Operation"):
        assert logger.timed_entries_open == 1
    
    assert logger.timed_entries_open == 0


def test_add_benchmarked_entry_nested():
    """Test nested benchmarked entries."""
    logger = EventLogger()
    
    with logger.add_benchmarked_entry("Outer operation"):
        assert logger.timed_entries_open == 1
        with logger.add_benchmarked_entry("Inner operation"):
            assert logger.timed_entries_open == 2
            time.sleep(0.01)
        assert logger.timed_entries_open == 1
    
    assert logger.timed_entries_open == 0
    assert len(logger.event_log) == 2
    assert "Outer operation" in logger.event_log[0]
    assert "Inner operation" in logger.event_log[1]
    # Inner operation should be indented
    assert logger.event_log[1].startswith("   ")


def test_str_empty_log():
    """Test string representation of empty event log."""
    logger = EventLogger()
    
    assert str(logger) == ""


def test_str_single_entry():
    """Test string representation with single entry."""
    logger = EventLogger()
    logger.add_entry("Single entry")
    
    assert str(logger) == "Single entry"


def test_str_multiple_entries():
    """Test string representation with multiple entries."""
    logger = EventLogger()
    logger.add_entry("First entry")
    logger.add_entry("Second entry")
    logger.add_entry("Third entry")
    
    expected = "First entry\nSecond entry\nThird entry"
    assert str(logger) == expected


def test_append_to_file_creates_new_file(tmp_path: Path):
    """Test that append_to_file creates a new file if it doesn't exist."""
    logger = EventLogger()
    logger.add_entry("Test entry 1")
    logger.add_entry("Test entry 2")
    
    target_file = tmp_path / "test_log.txt"
    logger.append_to_file(target_file)
    
    assert target_file.exists()
    content = target_file.read_text(encoding='utf-8')
    assert "Test entry 1" in content
    assert "Test entry 2" in content
    assert "=" in content  # Separator line


def test_append_to_file_with_path_object(tmp_path: Path):
    """Test that append_to_file works with Path object."""
    logger = EventLogger()
    logger.add_entry("Test entry")
    
    target_file = tmp_path / "test_log.txt"
    logger.append_to_file(target_file)
    
    assert target_file.exists()
    content = target_file.read_text(encoding='utf-8')
    assert "Test entry" in content


def test_append_to_file_appends_to_existing(tmp_path: Path):
    """Test that append_to_file appends to existing file."""
    logger1 = EventLogger()
    logger1.add_entry("First log entry")
    
    target_file = tmp_path / "test_log.txt"
    logger1.append_to_file(target_file)
    
    logger2 = EventLogger()
    logger2.add_entry("Second log entry")
    logger2.append_to_file(target_file)
    
    content = target_file.read_text(encoding='utf-8')
    assert "First log entry" in content
    assert "Second log entry" in content


def test_append_to_file_truncates_large_old_file(tmp_path: Path):
    """Test that large old files are truncated before appending."""
    target_file = tmp_path / "test_log.txt"
    
    # Create a large file (> 0.5 MB) that's old (> 6 hours)
    large_content = "x" * (600 * 1024)  # 600 KB
    target_file.write_text(large_content, encoding='utf-8')
    
    # Set modification time to 7 hours ago
    seven_hours_ago = time.time() - 7 * 60 * 60
    import os
    os.utime(target_file, (seven_hours_ago, seven_hours_ago))
    
    logger = EventLogger()
    logger.add_entry("New entry after truncation")
    logger.append_to_file(target_file)
    
    content = target_file.read_text(encoding='utf-8')
    # Old content should be gone
    assert "x" * 100 not in content
    # New content should be present
    assert "New entry after truncation" in content


def test_append_to_file_does_not_truncate_large_recent_file(tmp_path: Path):
    """Test that large recent files are not truncated."""
    target_file = tmp_path / "test_log.txt"
    
    # Create a large file (> 0.5 MB) that's recent
    large_content = "Recent content\n" * 50000  # > 0.5 MB
    target_file.write_text(large_content, encoding='utf-8')
    
    logger = EventLogger()
    logger.add_entry("New entry")
    logger.append_to_file(target_file)
    
    content = target_file.read_text(encoding='utf-8')
    # Old content should still be present
    assert "Recent content" in content
    # New content should also be present
    assert "New entry" in content


def test_append_to_file_does_not_truncate_small_old_file(tmp_path: Path):
    """Test that small old files are not truncated."""
    target_file = tmp_path / "test_log.txt"
    
    # Create a small file that's old
    small_content = "Old small content"
    target_file.write_text(small_content, encoding='utf-8')
    
    # Set modification time to 7 hours ago
    seven_hours_ago = time.time() - 7 * 60 * 60
    import os
    os.utime(target_file, (seven_hours_ago, seven_hours_ago))
    
    logger = EventLogger()
    logger.add_entry("New entry")
    logger.append_to_file(target_file)
    
    content = target_file.read_text(encoding='utf-8')
    # Old content should still be present (file is small)
    assert "Old small content" in content
    # New content should also be present
    assert "New entry" in content


def test_append_to_file_format(tmp_path: Path):
    """Test the format of appended content."""
    logger = EventLogger()
    logger.add_entry("Entry 1")
    logger.add_entry("Entry 2")
    
    target_file = tmp_path / "test_log.txt"
    logger.append_to_file(target_file)
    
    content = target_file.read_text(encoding='utf-8')
    
    # Should contain the log entries
    assert "Entry 1\nEntry 2" in content
    # Should contain separator
    assert "=" * 10 in content
    # Should have newlines around separator
    assert "\n\n=" in content
