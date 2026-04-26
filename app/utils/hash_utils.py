import hashlib
import json

def generate_file_hash(path, size, mtime):
    """
    Generate a SHA-256 hash for a file based on its metadata.

    Args:
        path (str): Relative or absolute path of the file.
        size (int): File size in bytes.
        mtime (float): File modification time.

    Returns:
        str: A SHA-256 hex string.
    """
    data = f"{path}|{size}|{mtime}"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def generate_collection_hash(hashes):
    """
    Generate a SHA-256 hash for a collection of hashes.
    Useful for category or library versioning.

    Args:
        hashes (list): A list of hash strings.

    Returns:
        str: A SHA-256 hex string.
    """
    # Sort hashes to ensure deterministic result regardless of input order
    sorted_hashes = sorted(hashes)
    data = "".join(sorted_hashes)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def generate_dict_hash(data_dict):
    """
    Generate a SHA-256 hash for a dictionary.

    Args:
        data_dict (dict): Data to hash.

    Returns:
        str: A SHA-256 hex string.
    """
    encoded_data = json.dumps(data_dict, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded_data).hexdigest()
