"""File utilities for K2Edit."""


def detect_encoding(content: str) -> str:
    """Detect encoding from file content.
    
    Args:
        content: The file content as a string
        
    Returns:
        The detected encoding name (e.g., 'UTF-8', 'ASCII', etc.)
    """
    if not content:
        return "UTF-8"
    
    # Try chardet if available
    try:
        import chardet
        content_bytes = content.encode('utf-8')
        result = chardet.detect(content_bytes)
        
        if result and result.get('encoding'):
            detected = result['encoding'].upper()
            confidence = result.get('confidence', 0)
            
            # Map common encodings to standard names
            encoding_map = {
                'ASCII': 'ASCII',
                'UTF-8': 'UTF-8',
                'UTF-16': 'UTF-16',
                'UTF-32': 'UTF-32',
                'ISO-8859-1': 'ISO-8859-1',
                'WINDOWS-1252': 'Windows-1252',
                'GB2312': 'GB2312',
                'GBK': 'GBK',
                'BIG5': 'Big5'
            }
            mapped_encoding = encoding_map.get(detected, detected)
            return mapped_encoding
    except ImportError:
        pass  # chardet not available, continue with fallback methods
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        # Fall back to other methods if chardet fails
        pass
    
    # Fallback: simple heuristic detection
    # Check for BOM markers
    if content.startswith('\ufeff'):
        return 'UTF-8-BOM'
    
    # Try to encode as different encodings
    try:
        content.encode('ascii')
        return 'ASCII'
    except UnicodeEncodeError:
        pass
    
    # Check for common non-ASCII patterns
    non_ascii_count = sum(1 for char in content if ord(char) > 127)
    if non_ascii_count > 0:
        # Contains non-ASCII characters, likely UTF-8
        try:
            content.encode('utf-8')
            return 'UTF-8'
        except UnicodeEncodeError:
            return 'UTF-8'  # Default fallback
    
    return 'UTF-8'  # Default for text content