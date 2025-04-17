# backend/utils_fs.py
import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

class FilesystemError(Exception):
    """Custom exception for filesystem util errors."""
    pass

def get_batch_dir(root_dir: str | Path, batch_id: str) -> Path | None:
    """Find the full path to a batch directory by its ID."""
    # Batch ID might be part of the directory name, need to scan
    # Expected structure: <root>/<skin>/<voice>/<batch_id_or_similar>/
    root = Path(root_dir)
    if not root.is_dir():
        raise FilesystemError(f"Audio root directory not found: {root_dir}")

    for skin_dir in root.iterdir():
        if not skin_dir.is_dir():
            continue
        for voice_dir in skin_dir.iterdir():
            if not voice_dir.is_dir():
                continue
            for potential_batch_dir in voice_dir.iterdir():
                # Check if the directory name *contains* the batch_id
                # This assumes batch_id is sufficiently unique
                if potential_batch_dir.is_dir() and batch_id in potential_batch_dir.name:
                    return potential_batch_dir
    return None

def load_metadata(batch_dir: str | Path) -> dict:
    """Loads and parses metadata.json from a batch directory."""
    meta_path = Path(batch_dir) / 'metadata.json'
    if not meta_path.is_file():
        raise FilesystemError(f"metadata.json not found in {batch_dir}")
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Basic validation (can be expanded)
        if not isinstance(data, dict) or 'takes' not in data or 'batch_id' not in data:
            raise ValueError("Invalid metadata format")
        return data
    except json.JSONDecodeError as e:
        raise FilesystemError(f"Error decoding metadata.json: {e}") from e
    except Exception as e:
        raise FilesystemError(f"Error loading metadata: {e}") from e

def save_metadata(batch_dir: str | Path, data: dict) -> None:
    """Atomically saves updated metadata to metadata.json."""
    batch_p = Path(batch_dir)
    meta_path = batch_p / 'metadata.json'
    temp_path = batch_p / f"metadata.json.tmp.{os.urandom(4).hex()}"

    try:
        # Validate basic structure before saving
        if not isinstance(data, dict) or 'takes' not in data or 'batch_id' not in data:
             raise ValueError("Attempted to save invalid metadata format")

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        # Atomic rename (on POSIX systems)
        os.rename(temp_path, meta_path)
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass # Ignore cleanup error
        raise FilesystemError(f"Error saving metadata: {e}") from e

def is_locked(batch_dir: str | Path) -> bool:
    """Checks for the presence of the LOCKED sentinel file."""
    return (Path(batch_dir) / 'LOCKED').exists()

def lock_batch(batch_dir: str | Path) -> None:
    """Creates the LOCKED sentinel file."""
    try:
        (Path(batch_dir) / 'LOCKED').touch(exist_ok=True)
    except Exception as e:
        raise FilesystemError(f"Error creating LOCK file: {e}") from e

def find_batches(root_dir: str | Path) -> list[dict]:
    """Scans the filesystem for batches and extracts key metadata."""
    batches = []
    root = Path(root_dir)
    if not root.is_dir():
        print(f"Warning: Audio root directory not found: {root_dir}")
        return []

    for skin_dir in root.iterdir():
        if not skin_dir.is_dir() or skin_dir.name.startswith('.'): continue
        for voice_dir in skin_dir.iterdir():
            if not voice_dir.is_dir() or voice_dir.name.startswith('.'): continue
            for batch_dir in voice_dir.iterdir():
                if not batch_dir.is_dir() or batch_dir.name.startswith('.'): continue
                meta_path = batch_dir / 'metadata.json'
                if meta_path.is_file():
                    try:
                        metadata = load_metadata(batch_dir) # Load the metadata
                        takes = metadata.get('takes', [])
                        params = metadata.get('generation_params', {})
                        
                        num_lines = len(set(t.get('line') for t in takes))
                        # Get variants from params, fallback to calculating max from takes
                        variants_per_line = params.get('variants_per_line', 0)
                        if variants_per_line == 0 and takes:
                             takes_by_line_count = {}
                             for t in takes:
                                 takes_by_line_count[t.get('line', '')] = takes_by_line_count.get(t.get('line', ''), 0) + 1
                             if takes_by_line_count:
                                 variants_per_line = max(takes_by_line_count.values())
                             
                        created_at_str = metadata.get('generated_at_utc')
                        # Attempt to parse date from metadata, fallback to batch ID name
                        created_at_sortable = None
                        try:
                            if created_at_str:
                                created_at_sortable = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).timestamp()
                            else: # Fallback: try parsing YYYYMMDD-HHMMSS from batch ID
                                dt_part = batch_dir.name.split('-')[0]
                                created_at_sortable = datetime.strptime(dt_part, "%Y%m%d").timestamp() # Only date part if time missing
                        except ValueError:
                           pass # Could not parse date

                        batches.append({
                            "batch_id": batch_dir.name,
                            "skin": skin_dir.name,
                            "voice": voice_dir.name,
                            "num_lines": num_lines,
                            "takes_per_line": variants_per_line, # Max/Configured takes per line
                            "num_takes": len(takes),
                            "created_at": created_at_str, # ISO string for display
                            "created_at_sortkey": created_at_sortable or 0, # Timestamp for sorting, fallback 0
                            "status": "Locked" if is_locked(batch_dir) else "Unlocked"
                        })
                    except Exception as e:
                        print(f"Warning: Skipping batch {batch_dir.name} due to metadata load/parse error: {e}")

    return batches

def rebuild_symlinks(batch_dir: str | Path, metadata: dict) -> None:
    """Clears ranked/ and recreates symlink tree based on ranks in metadata."""
    batch_p = Path(batch_dir)
    ranked_base_dir = batch_p / 'ranked'
    takes_dir = batch_p / 'takes'

    if not takes_dir.is_dir():
        raise FilesystemError(f"Takes directory not found: {takes_dir}")

    # Use a temporary directory for atomic replacement
    temp_ranked_dir = batch_p / f"ranked.tmp.{os.urandom(4).hex()}"

    try:
        temp_ranked_dir.mkdir()
        # Create subdirs 01-05
        for i in range(1, 6):
            (temp_ranked_dir / f"{i:02d}").mkdir()

        # Create symlinks based on metadata
        for take in metadata.get('takes', []):
            rank = take.get('rank')
            filename = take.get('file')

            if rank is not None and filename:
                try:
                    rank_val = int(rank)
                    if 1 <= rank_val <= 5:
                        target_rank_dir = temp_ranked_dir / f"{rank_val:02d}"
                        source_file = takes_dir / filename
                        link_path = target_rank_dir / filename

                        if source_file.exists():
                            # Symlink requires relative path from link location to target
                            # relative_target = os.path.relpath(source_file, target_rank_dir)
                            # Using absolute path for symlink target is often more robust
                            os.symlink(source_file.resolve(), link_path)
                        else:
                            print(f"Warning: Source file not found for symlink: {source_file}")
                except (ValueError, TypeError):
                    print(f"Warning: Invalid rank value '{rank}' for take '{filename}'")

        # Atomically replace old ranked dir with new one
        if ranked_base_dir.exists():
            # On some systems (like Windows), rename doesn't overwrite existing directories
            # shutil.rmtree might be needed first, but adds risk if interrupted
            # For POSIX, rename should work
            temp_backup_dir = batch_p / f"ranked.bak.{os.urandom(4).hex()}"
            os.rename(ranked_base_dir, temp_backup_dir)
            os.rename(temp_ranked_dir, ranked_base_dir)
            shutil.rmtree(temp_backup_dir) # Clean up backup
        else:
            os.rename(temp_ranked_dir, ranked_base_dir)

    except Exception as e:
        # Clean up temp dir on error
        if temp_ranked_dir.exists():
            try:
                shutil.rmtree(temp_ranked_dir)
            except OSError:
                pass
        raise FilesystemError(f"Error rebuilding symlinks: {e}") from e 