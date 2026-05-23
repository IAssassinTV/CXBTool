import os
import struct
import ctypes
import sys
from zlib import adler32, crc32
from hashlib import md5

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

def compress_LZO2A_999(data: bytes) -> bytes:
    src_len = len(data)
    dst_len_estimate = src_len + src_len // 16 + 64 + 3
    wrkmem_size = 8 * 16384 * ctypes.sizeof(ctypes.c_short)

    # Allocate buffers
    src = (ctypes.c_ubyte * src_len).from_buffer_copy(data)
    dst = (ctypes.c_ubyte * dst_len_estimate)()
    dst_len = ctypes.c_int(dst_len_estimate)
    wrkmem = (ctypes.c_ubyte * wrkmem_size)()

    # Call compression
    result = lzo2.lzo2a_999_compress(
        src,
        src_len,
        dst,
        ctypes.byref(dst_len),
        wrkmem
    )

    if result != 0:
        raise ValueError(f"LZO2A-999 compression failed with code {result}")

    return bytes(dst[:dst_len.value])

def read_xml_as_bytes(path: str) -> bytes:
    # Preserve the XML bytes exactly as stored on disk.
    with open(path, "rb") as f:
        xml_data = f.read()

    # Ensure the XML ends with a null byte
    if not xml_data.endswith(b'\x00'):
        xml_data += b'\x00'

    return xml_data

def build_file_data(xml_data: bytes) -> bytes:
    uncompressed_size = len(xml_data)

    # Split XML into chunks of DECOMP_BUFFER_SIZE
    chunks = [
        xml_data[i:i + DECOMP_BUFFER_SIZE]
        for i in range(0, len(xml_data), DECOMP_BUFFER_SIZE)
    ]

    blocks = []
    for chunk in chunks:
        de_size = len(chunk)
        comp_data = compress_LZO2A_999(chunk)
        en_size = len(comp_data)
        checksum = adler32(comp_data, 0)

        block = struct.pack(
            "<BIII",  # is_compressed = 1, de_size, en_size, checksum
            1,
            en_size,
            de_size,
            checksum,
        ) + comp_data

        blocks.append(block)

    # Build CompressedFileData
    return struct.pack(
        "<I Q H B H H",  # size, magic, version, algo, de_bufsize, en_bufsize
        uncompressed_size,
        MAGIC,
        VERSION,
        ALGO,
        DECOMP_BUFFER_SIZE,
        COMP_BUFFER_SIZE,
    ) + b"".join(blocks)

# Constants
MAGIC = 0x1004FA9957FBAA33
VERSION = 1
ALGO = 2  # LZO2A
DECOMP_BUFFER_SIZE = 32768
COMP_BUFFER_SIZE = 0

def pack_xml_files():
    # Input folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(script_dir, "xml_folder")

    # Ask user for full filename
    while True:
        try:
            filename = input("Enter full filename to save as (including .cxb or .smallpox extension): ").strip()
            if not filename:
                print("Filename cannot be empty.")
                continue
            if not filename.lower().endswith(('.cxb', '.smallpox')):
                print("Please save the file with either a .cxb or .smallpox extension.")
                continue
            output_file = os.path.join(script_dir, filename)
            output_ext = os.path.splitext(output_file)[1].lower()
            break
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return

    # Get all XML files from the input folder
    file_names = sorted(f for f in os.listdir(input_folder) if f.lower().endswith('.xml'))

    if output_ext == '.smallpox':
        preferred_name = os.path.splitext(os.path.basename(output_file))[0] + '.xml'
        preferred_path = os.path.join(input_folder, preferred_name)

        if os.path.exists(preferred_path):
            selected_files = [preferred_name]
        elif len(file_names) == 1:
            selected_files = file_names
        else:
            print("Available XML files:")
            for i, file in enumerate(file_names, 1):
                print(f"{i}. {file}")

            while True:
                try:
                    selection = input(f"Select the XML file to pack (1-{len(file_names)}): ").strip()
                    idx = int(selection) - 1
                    if 0 <= idx < len(file_names):
                        selected_files = [file_names[idx]]
                        break
                    print(f"Please enter a number between 1 and {len(file_names)}")
                except ValueError:
                    print("Please enter a valid number")

        name = selected_files[0]
        path = os.path.join(input_folder, name)
        print(f"Processing {name}...")

        try:
            xml_data = read_xml_as_bytes(path)
        except Exception as e:
            print(f"⚠️  Warning: Could not process {name} - {str(e)}.")
            return

        file_data = build_file_data(xml_data)

        with open(output_file, "wb") as f:
            f.write(file_data + b"\x01")

        print(f"✅ Successfully created {output_file} with 1 XML file")
        return

    file_infos = []
    file_datas = []

    for name in file_names:
        path = os.path.join(input_folder, name)
        print(f"Processing {name}...")

        try:
            xml_data = read_xml_as_bytes(path)
        except Exception as e:
            print(f"⚠️  Warning: Could not process {name} - {str(e)}. Skipping...")
            continue

        file_data = build_file_data(xml_data)
        file_datas.append(file_data)

        # Build FileInfo
        name_buffer = name.split(".")[0].encode("ascii").ljust(40, b"\x00")
        size_str = str(len(file_data)).encode("ascii").ljust(8, b"\x00")
        file_info = name_buffer + size_str
        file_infos.append(file_info)

    # Write final CXB file
    with open(output_file, "wb") as f:
        # Write file infos
        all_infos = b''.join(file_infos)
        f.write(all_infos)

        # Write end marker
        f.write(b"0".ljust(48, b"\x00"))

        # Write file datas
        all_data = b''.join(file_datas)
        f.write(all_data)

    print(f"✅ Successfully created {output_file} with {len(file_names)} XML files")

if __name__ == "__main__":
    pack_xml_files()