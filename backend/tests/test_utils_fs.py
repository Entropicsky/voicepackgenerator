# backend/tests/test_utils_fs.py
import pytest
import json
import os
from pathlib import Path
# Use relative import
from .. import utils_fs

# Pytest fixture provided by pyfakefs
# fs is the fake filesystem object

# --- Test Data ---
dummy_metadata = {
    "batch_id": "20250101-120000-test",
    "skin_name": "TestSkin",
    "voice_name": "TestVoice-abc",
    "generated_at_utc": "2025-01-01T12:00:00Z",
    "generation_params": {},
    "ranked_at_utc": None,
    "takes": [
        {"file": "line1_take1.mp3", "line": "line1", "script_text": "t1", "take_number": 1, "rank": 1, "ranked_at": None},
        {"file": "line1_take2.mp3", "line": "line1", "script_text": "t2", "take_number": 2, "rank": None, "ranked_at": None},
        {"file": "line2_take1.mp3", "line": "line2", "script_text": "t3", "take_number": 1, "rank": 5, "ranked_at": None},
    ]
}

# --- Fixtures ---

@pytest.fixture
def fake_batch(fs): # fs is the pyfakefs fixture
    """Creates a fake batch structure in the fake filesystem."""
    root = Path('/test_output')
    skin = root / 'TestSkin'
    voice = skin / 'TestVoice-abc'
    batch = voice / '20250101-120000-test'
    takes = batch / 'takes'
    ranked = batch / 'ranked'

    fs.create_dir(takes)
    fs.create_dir(ranked)
    # Create dummy take files
    fs.create_file(takes / 'line1_take1.mp3', contents='audio11')
    fs.create_file(takes / 'line1_take2.mp3', contents='audio12')
    fs.create_file(takes / 'line2_take1.mp3', contents='audio21')

    # Create metadata file
    fs.create_file(batch / 'metadata.json', contents=json.dumps(dummy_metadata, indent=2))

    return root, batch

# --- Tests ---

def test_get_batch_dir_found(fs, fake_batch):
    root, _ = fake_batch
    batch_id = "20250101-120000-test"
    found_dir = utils_fs.get_batch_dir(root, batch_id)
    assert found_dir is not None
    assert found_dir.name == batch_id
    assert found_dir.is_dir()

def test_get_batch_dir_not_found(fs, fake_batch):
    root, _ = fake_batch
    assert utils_fs.get_batch_dir(root, "nonexistent-batch") is None

def test_get_batch_dir_root_not_exist(fs):
    with pytest.raises(utils_fs.FilesystemError, match="Audio root directory not found"):
        utils_fs.get_batch_dir("/nonexistent_root", "any_batch")

def test_load_metadata_success(fs, fake_batch):
    _, batch_dir = fake_batch
    metadata = utils_fs.load_metadata(batch_dir)
    assert metadata["batch_id"] == "20250101-120000-test"
    assert len(metadata["takes"]) == 3

def test_load_metadata_not_found(fs, fake_batch):
    root, _ = fake_batch
    non_batch_dir = root / "TestSkin" / "TestVoice-abc" / "empty_dir"
    fs.create_dir(non_batch_dir)
    with pytest.raises(utils_fs.FilesystemError, match="metadata.json not found"):
        utils_fs.load_metadata(non_batch_dir)

def test_load_metadata_invalid_json(fs, fake_batch):
    _, batch_dir = fake_batch
    # Remove the existing valid file first
    fs.remove(batch_dir / 'metadata.json')
    # Now create the invalid one
    fs.create_file(batch_dir / 'metadata.json', contents='this is not json')
    with pytest.raises(utils_fs.FilesystemError, match="Error decoding metadata.json"):
        utils_fs.load_metadata(batch_dir)

def test_save_metadata_success(fs, fake_batch):
    _, batch_dir = fake_batch
    metadata = utils_fs.load_metadata(batch_dir)
    metadata["takes"][1]["rank"] = 3 # Modify data
    metadata["ranked_at_utc"] = "NOW"

    utils_fs.save_metadata(batch_dir, metadata)

    # Reload and check
    reloaded_metadata = utils_fs.load_metadata(batch_dir)
    assert reloaded_metadata["takes"][1]["rank"] == 3
    assert reloaded_metadata["ranked_at_utc"] == "NOW"
    assert not list(batch_dir.glob("metadata.json.tmp*")) # Check temp file cleanup

def test_is_locked_false(fs, fake_batch):
    _, batch_dir = fake_batch
    assert not utils_fs.is_locked(batch_dir)

def test_is_locked_true(fs, fake_batch):
    _, batch_dir = fake_batch
    fs.create_file(batch_dir / 'LOCKED')
    assert utils_fs.is_locked(batch_dir)

def test_lock_batch(fs, fake_batch):
    _, batch_dir = fake_batch
    assert not (batch_dir / 'LOCKED').exists()
    utils_fs.lock_batch(batch_dir)
    assert (batch_dir / 'LOCKED').exists()

def test_find_batches(fs, fake_batch):
    root, _ = fake_batch
    # Add another dummy batch
    fs.create_dir(root / "OtherSkin/OtherVoice/batch2")
    fs.create_file(root / "OtherSkin/OtherVoice/batch2/metadata.json", contents='{"batch_id": "batch2", "takes": []}')
    # Add an invalid dir
    fs.create_dir(root / "invalid_dir_no_meta")

    batches = utils_fs.find_batches(root)
    assert len(batches) == 2
    assert {"skin": "TestSkin", "voice": "TestVoice-abc", "batch_id": "20250101-120000-test"} in batches
    assert {"skin": "OtherSkin", "voice": "OtherVoice", "batch_id": "batch2"} in batches

def test_rebuild_symlinks_success(fs, fake_batch):
    _, batch_dir = fake_batch
    metadata = utils_fs.load_metadata(batch_dir)
    # Ensure some ranks are set for testing
    metadata["takes"][0]["rank"] = 1
    metadata["takes"][2]["rank"] = 5
    utils_fs.save_metadata(batch_dir, metadata)

    utils_fs.rebuild_symlinks(batch_dir, metadata)

    ranked_dir = batch_dir / 'ranked'
    rank1_dir = ranked_dir / '01'
    rank5_dir = ranked_dir / '05'
    rank_other_dir = ranked_dir / '02' # Should be empty

    assert ranked_dir.is_dir()
    assert rank1_dir.is_dir()
    assert rank5_dir.is_dir()
    assert rank_other_dir.is_dir()

    link1 = rank1_dir / "line1_take1.mp3"
    link5 = rank5_dir / "line2_take1.mp3"
    assert link1.is_symlink()
    assert link5.is_symlink()

    # Check link targets (using resolve in fake fs)
    target1 = (batch_dir / "takes" / "line1_take1.mp3").resolve()
    target5 = (batch_dir / "takes" / "line2_take1.mp3").resolve()
    assert link1.resolve() == target1
    assert link5.resolve() == target5

    # Check other rank folders are empty
    assert not list(rank_other_dir.glob("*.mp3"))

def test_rebuild_symlinks_clears_old(fs, fake_batch):
    _, batch_dir = fake_batch
    metadata = utils_fs.load_metadata(batch_dir)
    ranked_dir = batch_dir / 'ranked'
    rank3_dir = ranked_dir / '03'
    fs.create_dir(rank3_dir)
    fs.create_file(rank3_dir / "old_link.mp3") # Create a dummy old file

    # Rebuild with metadata that has no rank 3 files
    utils_fs.rebuild_symlinks(batch_dir, metadata)

    assert not (ranked_dir / "03" / "old_link.mp3").exists()
    assert (ranked_dir / "01" / "line1_take1.mp3").is_symlink() # Check a correct link is still there 