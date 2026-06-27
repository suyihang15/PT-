"""
Bencode encoding/decoding for BitTorrent protocol.

Bencode types:
- Byte strings: <length>:<string>
- Integers: i<number>e
- Lists: l<items>e
- Dictionaries: d<keys/values>e

All keys in dictionaries are byte strings.
All strings are byte strings (NOT Unicode).
"""


def bencode_decode(data, offset=0):
    """Decode a bencoded value starting at offset. Returns (value, next_offset)."""
    if offset >= len(data):
        raise ValueError('Unexpected end of data')

    char = data[offset:offset + 1]

    if char == b'i':
        # Integer
        end = data.index(b'e', offset)
        value = int(data[offset + 1:end])
        return value, end + 1

    elif char == b'l':
        # List
        offset += 1
        result = []
        while offset < len(data) and data[offset:offset + 1] != b'e':
            item, offset = bencode_decode(data, offset)
            result.append(item)
        return result, offset + 1

    elif char == b'd':
        # Dictionary
        offset += 1
        result = {}
        while offset < len(data) and data[offset:offset + 1] != b'e':
            key, offset = bencode_decode(data, offset)
            if not isinstance(key, bytes):
                raise ValueError('Dictionary keys must be byte strings')
            value, offset = bencode_decode(data, offset)
            result[key] = value
        return result, offset + 1

    elif char in b'0123456789':
        # Byte string: <length>:<bytes>
        colon = data.index(b':', offset)
        length = int(data[offset:colon])
        start = colon + 1
        end = start + length
        return data[start:end], end

    else:
        raise ValueError(f'Unexpected character at offset {offset}: {char!r}')


def bencode_encode(value):
    """Encode a Python value to bencode bytes."""
    if isinstance(value, bytes):
        return f'{len(value)}:'.encode() + value
    elif isinstance(value, str):
        encoded = value.encode('utf-8')
        return f'{len(encoded)}:'.encode() + encoded
    elif isinstance(value, int):
        return f'i{value}e'.encode()
    elif isinstance(value, list):
        items = b''.join(bencode_encode(item) for item in value)
        return b'l' + items + b'e'
    elif isinstance(value, dict):
        items = b''
        for k, v in value.items():
            items += bencode_encode(k) + bencode_encode(v)
        return b'd' + items + b'e'
    else:
        raise ValueError(f'Cannot bencode type {type(value)}: {value!r}')


def parse_torrent_file(filepath_or_data):
    """Parse a .torrent file and return its metadata."""
    if isinstance(filepath_or_data, bytes):
        data = filepath_or_data
    else:
        with open(filepath_or_data, 'rb') as f:
            data = f.read()

    torrent = bencode_decode(data)[0]

    if not isinstance(torrent, dict):
        raise ValueError('Invalid torrent file: top level is not a dictionary')

    info = torrent.get(b'info')
    if not info:
        raise ValueError('Invalid torrent file: missing info dictionary')

    # Calculate info_hash (SHA1 of bencoded info dict)
    import hashlib
    info_encoded = bencode_encode(info)
    info_hash = hashlib.sha1(info_encoded).hexdigest().upper()

    # Extract file list
    files = []
    total_size = 0

    if b'files' in info:
        # Multi-file torrent
        for f in info[b'files']:
            path_parts = [p.decode('utf-8', errors='replace') for p in f[b'path']]
            file_path = '/'.join(path_parts)
            file_size = f[b'length']
            files.append({'path': file_path, 'size': file_size})
            total_size += file_size
    else:
        # Single file torrent
        name = info[b'name'].decode('utf-8', errors='replace')
        file_size = info[b'length']
        files.append({'path': name, 'size': file_size})
        total_size = file_size

    # Extract metadata
    piece_length = info[b'piece length']
    pieces = info[b'pieces']
    piece_count = len(pieces) // 20

    result = {
        'info_hash': info_hash,
        'name': info[b'name'].decode('utf-8', errors='replace'),
        'size': total_size,
        'file_count': len(files),
        'files': files,
        'piece_length': piece_length,
        'piece_count': piece_count,
        'is_private': info.get(b'private', 0) == 1,
        'created_by': torrent.get(b'created by', b'').decode('utf-8', errors='replace'),
        'creation_date': torrent.get(b'creation date', None),
        'encoding': torrent.get(b'encoding', b'UTF-8').decode('utf-8', errors='replace'),
    }

    return result
