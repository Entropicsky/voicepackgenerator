import pytest
from unittest import mock
import os
from backend.utils_prompts import _get_elevenlabs_rules

# Use pyfakefs for filesystem mocking
from pyfakefs.fake_filesystem_unittest import Patcher

MOCK_RULES_CONTENT_VALID = """
Some text before rules.

### ElevenLabs Prompt-Writing Rules:

Rule 1: Do this.
Rule 2: Do that.
<break time='1s'/>

### Example Agent Prompt:
Ignore this part.
"""

MOCK_RULES_CONTENT_NO_MARKER = """
Some text, but no rules marker.
"""

MOCK_RULES_CONTENT_NO_END_MARKER = """
Some text before rules.

### ElevenLabs Prompt-Writing Rules:

Rule 1: Do this.
Rule 2: Do that.
This text should be included.
"""

EXPECTED_RULES_VALID = """Rule 1: Do this.
Rule 2: Do that.
<break time='1s'/>"""

EXPECTED_RULES_NO_END_MARKER = """Rule 1: Do this.
Rule 2: Do that.
This text should be included."""

@pytest.fixture
def fake_fs():
    """Provides a fake filesystem using pyfakefs."""
    with Patcher() as patcher:
        yield patcher.fs

def test_get_elevenlabs_rules_success(fake_fs):
    """Test successful extraction of rules."""
    rules_path = "/fake/prompts/scripthelp.md"
    fake_fs.create_file(rules_path, contents=MOCK_RULES_CONTENT_VALID)
    
    rules = _get_elevenlabs_rules(rules_path)
    assert rules == EXPECTED_RULES_VALID

def test_get_elevenlabs_rules_no_end_marker(fake_fs):
    """Test extraction when the end marker is missing."""
    rules_path = "/fake/prompts/scripthelp.md"
    fake_fs.create_file(rules_path, contents=MOCK_RULES_CONTENT_NO_END_MARKER)
    
    rules = _get_elevenlabs_rules(rules_path)
    assert rules == EXPECTED_RULES_NO_END_MARKER

def test_get_elevenlabs_rules_no_start_marker(fake_fs):
    """Test failure when the start marker is missing."""
    rules_path = "/fake/prompts/scripthelp.md"
    fake_fs.create_file(rules_path, contents=MOCK_RULES_CONTENT_NO_MARKER)
    
    rules = _get_elevenlabs_rules(rules_path)
    assert rules is None

def test_get_elevenlabs_rules_file_not_found(fake_fs):
    """Test failure when the file doesn't exist."""
    rules_path = "/non/existent/path.md"
    rules = _get_elevenlabs_rules(rules_path)
    assert rules is None

@mock.patch('builtins.open', side_effect=OSError("Permission denied"))
def test_get_elevenlabs_rules_os_error(mock_open, fake_fs):
    """Test failure on generic OS error during file read."""
    rules_path = "/fake/prompts/scripthelp.md"
    # File needs to exist for open to be called, even though open is mocked
    fake_fs.create_file(rules_path, contents="dummy") 
    
    rules = _get_elevenlabs_rules(rules_path)
    assert rules is None
    mock_open.assert_called_once_with(rules_path, 'r', encoding='utf-8') 