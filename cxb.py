import struct
import string
import re
import os
import sys
import ctypes
from zlib import adler32
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

def format_xml_minimal(file_path):
    """
    Format an XML file with proper indentation and structure.
    This function is called automatically after extraction.
    """
    try:
        # Read the file in binary to preserve exact bytes
        with open(file_path, 'rb') as f:
            content = f.read().decode('utf-8')
        
        # Parse the XML content
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            print(f"Warning: XML parsing error in {file_path}: {e}")
            # Try to fix common XML issues
            content = fix_xml_issues(content)
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                print(f"Could not fix XML structure in {file_path}")
                return False
        
        # Convert to string with proper formatting
        rough_string = ET.tostring(root, encoding='unicode')
        
        # Parse with minidom for pretty printing
        reparsed = minidom.parseString(rough_string)
        
        # Format with proper indentation
        formatted_xml = reparsed.toprettyxml(indent="  ", encoding=None)
        
        # Clean up the formatting - remove extra blank lines and fix XML declaration
        lines = formatted_xml.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            line = line.rstrip()
            if line:  # Skip empty lines
                # Fix XML declaration to be on first line without extra whitespace
                if line.strip().startswith('<?xml'):
                    cleaned_lines.append('<?xml version="1.0"?>')
                else:
                    # Keep all other lines including root elements
                    cleaned_lines.append(line)
        
        # Join lines and ensure proper ending
        result = '\n'.join(cleaned_lines)
        if not result.endswith('\n'):
            result += '\n'
        
        # Write back the file
        with open(file_path, 'wb') as f:
            f.write(result.encode('utf-8'))
            
        print(f"Formatted: {os.path.basename(file_path)}")
        return True
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return False

def fix_xml_issues(content):
    """
    Fix common XML structural issues.
    """
    # Remove null bytes if present
    content = content.replace('\x00', '')
    
    # Ensure content starts with XML declaration if it has one
    if not content.strip().startswith('<?xml') and '<root>' in content:
        content = '<?xml version="1.0"?>' + content
    
    # Fix missing closing tags (basic attempt)
    # This is a simple fix - more complex issues would require more sophisticated parsing
    content = re.sub(r'<([^<>]+)([^/>]*)>', lambda m: f'<{m.group(1)}{m.group(2)}>' if m.group(2).endswith('/') else f'<{m.group(1)}{m.group(2)}>', content)
    
    return content

# Try to load LZO2 library with different possible names/paths
lzo2 = None
lzo_paths = [
    'lzo2.dll',  # Common Windows name
    'liblzo2-2.dll',  # Alternative Windows name
    'liblzo2.so',  # Linux name
    'liblzo2.dylib'  # macOS name
]

if sys.platform == 'win32':
    # On Windows, try to find the DLL in the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lzo_paths = [os.path.join(script_dir, path) for path in lzo_paths] + lzo_paths

for path in lzo_paths:
    try:
        lzo2 = ctypes.CDLL(path)
        print(f"Successfully loaded LZO2 library from: {path}")
        break
    except (OSError, FileNotFoundError):
        continue

if lzo2 is None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir, 'lzo2.dll')
    
    print("="*80)
    print("LZO2 library not found. To fix this:")
    print(f"1. Download 'lzo2.dll' from a trusted source")
    print(f"2. Save it to: {dll_path}")
    print("3. Run the script again")
    print("="*80)
    
    # Create a placeholder file with instructions
    with open(os.path.join(script_dir, 'GET_LZO2_DLL.txt'), 'w') as f:
        f.write("INSTRUCTIONS TO GET LZO2.DLL\n")
        f.write("="*40 + "\n")
        f.write("1. Download 'lzo2.dll' from one of these sources:\n")
        f.write("   - https://www.dll-files.com/lzo2.dll.html\n")
        f.write("   - Or search for 'lzo2.dll download for Windows'\n")
        f.write(f"2. Place the downloaded 'lzo2.dll' in this directory:\n   {script_dir}\\n")
        f.write("3. Run the script again\n")
    
    raise ImportError("LZO2 library not found. Please follow the instructions above.")

def decompress_LZO2A(compressed_data, expected_decompressed_size):
    # allocate buffers
    src = ctypes.create_string_buffer(compressed_data)
    dst = ctypes.create_string_buffer(expected_decompressed_size)

    result = lzo2.lzo2a_decompress_safe(
        ctypes.byref(src),
        len(compressed_data),
        ctypes.byref(dst),
        ctypes.pointer(ctypes.c_int(expected_decompressed_size)),
        None
    )
    if result:
        raise ValueError(f"Decompression failed with code {result}")

    print("Decompressed successfully")
    return dst.raw

# Create output directory if it doesn't exist
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "xml_folder")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created directory: {os.path.abspath(output_dir)}")

# Find all .cxb files in the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
cxb_files = [f for f in os.listdir(script_dir) if f.lower().endswith('.cxb')]

if not cxb_files:
    raise FileNotFoundError(f"No .cxb files found in the script directory: {script_dir}")

# Let user select a file
print("\nAvailable .cxb files:")
for i, file in enumerate(cxb_files, 1):
    print(f"{i}. {file}")

while True:
    try:
        selection = input(f"\nSelect a file (1-{len(cxb_files)}, or press Enter for first file): ")
        if not selection:
            binary_file_path = os.path.join(script_dir, cxb_files[0])  # Default to first file if no input
            break
        idx = int(selection) - 1
        if 0 <= idx < len(cxb_files):
            binary_file_path = os.path.join(script_dir, cxb_files[idx])
            break
        print(f"Please enter a number between 1 and {len(cxb_files)}")
    except ValueError:
        print("Please enter a valid number")

print(f"\nSelected file: {binary_file_path}")

magic_number = 0x1004FA9957FBAA33
magic_bytes = struct.pack("<Q", magic_number)

with open(binary_file_path, "rb") as f:
    data = f.read()

indices = []
i = data.find(magic_bytes)
while i != -1:
    indices.append(i)
    i = data.find(magic_bytes, i + 1)

def create_dict(strings):
    result = {}
    i = 0
    while i < len(strings) - 1:
        key = strings[i]
        value = strings[i + 1]
        if value and value[0].isdigit():
            result[key] = int(value)
            i += 2
        else:
            break
    return result

def extract_starting_bytes(data, n, to_int = False):
    d = data[:n]
    if to_int:
        d = int.from_bytes(d, byteorder="little")
    return d, data[n:]

pre_magic_data = data[:indices[0]]

# convert to string
decoded = ''.join(chr(b) if chr(b) in string.printable else ' ' for b in pre_magic_data)

# remove padding
segments = [s for s in re.split(r'\s+', decoded) if s]

print("Extracted segments:")
segments = [(segments[i], int(segments[i + 1])) for i in range(0, len(segments) - 2, 2)]
print("XML, size:", segments)
for i in range(len(indices)):
    print(f"Analyzing {segments[i][0]}")
    index = indices[i]
    start = index - 4
    end = start + segments[i][1]
    s = data[start:end]
    size, s = extract_starting_bytes(s, 4)
    size = int.from_bytes(size, byteorder='little') # size of the actual XML # type: ignore
    magic, s = extract_starting_bytes(s, 8)
    version, s = extract_starting_bytes(s, 2, True)
    algo, s = extract_starting_bytes(s, 1, True)
    en_bufsize, s = extract_starting_bytes(s, 2, True) # size of buffer to hold compressed data
    de_bufsize, s = extract_starting_bytes(s, 2, True) # size of buffer to hold decompressed data
    print(f"""Segment data:
    Uncompressed XML size: {size}
    Magic: {magic}
    Version: {version}
    Algo: {algo}
    Decompression buffer size: {de_bufsize}
    Compression buffer size: {en_bufsize}""")
    ref = f"{segments[i][0]}.xml"
    if os.path.exists(ref):
        print(f"\nReference file size: {os.path.getsize(ref)}\n")
    else:
        print()

    try:
        offset = 0  # Start of binary payload
        chunks = []

        while offset < len(s):
            try:
                # Read compression flag
                is_compressed = s[offset]
                offset += 1

                if is_compressed:
                    # Read compressed block header
                    en_size = int.from_bytes(s[offset:offset+4], "little") # size of compressed data in buffer
                    offset += 4
                    de_size = int.from_bytes(s[offset:offset+4], "little") # size of decompressed data in buffer
                    offset += 4
                    checksum = int.from_bytes(s[offset:offset+4], "little")
                    offset += 4
                    print(f"""Block data:
                            Compressed: {is_compressed}
                            Decompression size: {de_size}
                            Compression size: {en_size}
                            Checksum: {checksum}
                        """)
                    # Extract compressed data
                    comp_data = s[offset:offset+en_size]
                    offset += en_size

                    # Validate checksum
                    calc_checksum = adler32(comp_data, 0)
                    if calc_checksum != checksum:
                        print(f"⚠️ Checksum mismatch at offset {offset}: expected {hex(checksum)}, got {hex(calc_checksum)}")

                    # Decompress
                    chunk = decompress_LZO2A(comp_data, de_size)
                    chunks.append(chunk)
                else:
                    # Uncompressed block
                    data_size = int.from_bytes(s[offset:offset+4], "little")
                    print(f"""Block data:
                        Compressed: {is_compressed}
                        Data size: {data_size}
                        """)
                    offset += 4
                    chunk = s[offset:offset+data_size]
                    offset += data_size
                    chunks.append(chunk)

            except Exception as e:
                print(f"❌ Error at offset {offset}: {e}")
                break

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {os.path.abspath(output_dir)}")

        # Combine all chunks
        full_data = b"".join(chunks)
        if full_data:
            if full_data.endswith(b'\x00'):
                full_data = full_data[:-1]
            f_out = os.path.join(output_dir, f"{segments[i][0]}.xml")
            with open(f_out, "wb") as f:
                f.write(full_data)
            print(f"Saved decompressed data to {f_out}")
            
            # Format the extracted XML file
            format_xml_minimal(f_out)
    except Exception as e:
        print(f"Decompression failed: {e}")

if __name__ == "__main__":
    # Create output directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xml_folder = os.path.join(script_dir, "xml_folder")
    if not os.path.exists(xml_folder):
        os.makedirs(xml_folder)
        print(f"Created directory: {os.path.abspath(xml_folder)}")
        
    # Run the extraction and formatting
    try:
        # The actual execution happens when the script is imported
        pass
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
