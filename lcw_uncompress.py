#!/usr/bin/env python3
"""
LCW Decompressor and PNG Generator
Decompresses LCW-compressed data and generates PNG files using color palettes.
Based on Westwood Studios' LCW compression algorithm.
"""

import struct
import argparse
from PIL import Image
import os


class LCWDecompressor:
    """LCW decompression implementation based on Westwood Studios algorithm."""
    
    def __init__(self):
        pass
    
    def decompress(self, compressed_data):
        """
        Decompress LCW-encoded data.
        
        Args:
            compressed_data (bytes): The compressed data to decompress
            
        Returns:
            bytes: The decompressed data
        """
        source_ptr = 0
        dest_data = bytearray()
        
        while source_ptr < len(compressed_data):
            # Read operation code
            op_code = compressed_data[source_ptr]
            source_ptr += 1
            
            if not (op_code & 0x80):
                # Short copy from destination (op_code & 0x7F)
                count = (op_code >> 4) + 3
                if source_ptr >= len(compressed_data):
                    break
                    
                offset = compressed_data[source_ptr] + ((op_code & 0x0F) << 8)
                source_ptr += 1
                
                copy_start = len(dest_data) - offset
                if copy_start < 0:
                    copy_start = 0
                
                for i in range(count):
                    if copy_start + i < len(dest_data):
                        dest_data.append(dest_data[copy_start + i])
                    else:
                        dest_data.append(0)
                        
            else:
                if not (op_code & 0x40):
                    if op_code == 0x80:
                        # End of data
                        break
                    else:
                        # Medium copy from source
                        count = op_code & 0x3F
                        for i in range(count):
                            if source_ptr < len(compressed_data):
                                dest_data.append(compressed_data[source_ptr])
                                source_ptr += 1
                            else:
                                dest_data.append(0)
                else:
                    if op_code == 0xFE:
                        # Long run
                        if source_ptr + 2 >= len(compressed_data):
                            break
                        count = compressed_data[source_ptr] + (compressed_data[source_ptr + 1] << 8)
                        data_byte = compressed_data[source_ptr + 2]
                        source_ptr += 3
                        
                        for i in range(count):
                            dest_data.append(data_byte)
                            
                    elif op_code == 0xFF:
                        # Long copy from destination
                        if source_ptr + 3 >= len(compressed_data):
                            break
                        count = compressed_data[source_ptr] + (compressed_data[source_ptr + 1] << 8)
                        offset = compressed_data[source_ptr + 2] + (compressed_data[source_ptr + 3] << 8)
                        source_ptr += 4
                        
                        for i in range(count):
                            if offset + i < len(dest_data):
                                dest_data.append(dest_data[offset + i])
                            else:
                                dest_data.append(0)
                    else:
                        # Medium copy from destination
                        if source_ptr + 1 >= len(compressed_data):
                            break
                        count = (op_code & 0x3F) + 3
                        offset = compressed_data[source_ptr] + (compressed_data[source_ptr + 1] << 8)
                        source_ptr += 2
                        
                        for i in range(count):
                            if offset + i < len(dest_data):
                                dest_data.append(dest_data[offset + i])
                            else:
                                dest_data.append(0)
        
        return bytes(dest_data)


class PaletteLoader:
    """Load color palettes from various formats."""
    
    @staticmethod
    def load_palette(palette_file):
        """
        Load a color palette from file.
        Supports .pal (JASC-PAL), .act (Adobe Color Table), and .gpl (GIMP Palette) formats.
        
        Args:
            palette_file (str): Path to palette file
            
        Returns:
            list: List of (R, G, B) tuples representing the palette
        """
        _, ext = os.path.splitext(palette_file.lower())
        
        if ext == '.pal':
            return PaletteLoader._load_jasc_pal(palette_file)
        elif ext == '.act':
            return PaletteLoader._load_act(palette_file)
        elif ext == '.gpl':
            return PaletteLoader._load_gpl(palette_file)
        else:
            raise ValueError(f"Unsupported palette format: {ext}")
    
    @staticmethod
    def _load_jasc_pal(filename):
        """Load JASC-PAL format palette."""
        palette = []
        with open(filename, 'r') as f:
            lines = f.readlines()
            
        if len(lines) < 3 or lines[0].strip() != "JASC-PAL":
            raise ValueError("Invalid JASC-PAL file format")
        
        version = lines[1].strip()
        num_colors = int(lines[2].strip())
        
        for i in range(3, min(3 + num_colors, len(lines))):
            rgb = lines[i].strip().split()
            if len(rgb) >= 3:
                r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
                palette.append((r, g, b))
        
        # Pad to 256 colors if needed
        while len(palette) < 256:
            palette.append((0, 0, 0))
            
        return palette
    
    @staticmethod
    def _load_act(filename):
        """Load Adobe Color Table format palette."""
        palette = []
        with open(filename, 'rb') as f:
            data = f.read()
        
        # ACT files contain 256 RGB triplets (768 bytes)
        for i in range(0, min(768, len(data)), 3):
            if i + 2 < len(data):
                r, g, b = data[i], data[i + 1], data[i + 2]
                palette.append((r, g, b))
        
        # Pad to 256 colors if needed
        while len(palette) < 256:
            palette.append((0, 0, 0))
            
        return palette
    
    @staticmethod
    def _load_gpl(filename):
        """Load GIMP Palette format."""
        palette = []
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        if not lines[0].startswith("GIMP Palette"):
            raise ValueError("Invalid GIMP Palette file format")
        
        for line in lines[1:]:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('Name:') and not line.startswith('Columns:'):
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                        palette.append((r, g, b))
                    except ValueError:
                        continue
        
        # Pad to 256 colors if needed
        while len(palette) < 256:
            palette.append((0, 0, 0))
            
        return palette


def create_png_from_indexed_data(indexed_data, palette, width, height, output_file):
    """
    Create a PNG file from indexed color data and a palette.
    
    Args:
        indexed_data (bytes): The indexed color data
        palette (list): List of (R, G, B) tuples
        width (int): Image width
        height (int): Image height  
        output_file (str): Output PNG filename
    """
    # Create a new image in palette mode
    img = Image.new('P', (width, height))
    
    # Set the palette
    palette_data = []
    for r, g, b in palette:
        palette_data.extend([r, g, b])
    
    # Pad palette to 256 colors if needed
    while len(palette_data) < 768:  # 256 * 3
        palette_data.extend([0, 0, 0])
    
    img.putpalette(palette_data)
    
    # Put the indexed data
    if len(indexed_data) != width * height:
        print(f"Warning: Data size ({len(indexed_data)}) doesn't match image dimensions ({width}x{height}={width*height})")
        # Pad or truncate data as needed
        if len(indexed_data) < width * height:
            indexed_data = indexed_data + bytes(width * height - len(indexed_data))
        else:
            indexed_data = indexed_data[:width * height]
    
    img.putdata(indexed_data)
    img.save(output_file, 'PNG')
    print(f"PNG saved as: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='LCW Decompressor and PNG Generator')
    parser.add_argument('input_file', help='Input LCW compressed file')
    parser.add_argument('palette_file', help='Color palette file (.pal, .act, or .gpl)')
    parser.add_argument('output_file', help='Output PNG file')
    parser.add_argument('--width', type=int, required=True, help='Image width in pixels')
    parser.add_argument('--height', type=int, required=True, help='Image height in pixels')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        # Load the compressed data
        if args.verbose:
            print(f"Loading compressed data from: {args.input_file}")
        
        with open(args.input_file, 'rb') as f:
            compressed_data = f.read()
        
        if args.verbose:
            print(f"Compressed data size: {len(compressed_data)} bytes")
        
        # Decompress the data
        decompressor = LCWDecompressor()
        decompressed_data = decompressor.decompress(compressed_data)
        
        if args.verbose:
            print(f"Decompressed data size: {len(decompressed_data)} bytes")
        
        # Load the palette
        if args.verbose:
            print(f"Loading palette from: {args.palette_file}")
        
        palette = PaletteLoader.load_palette(args.palette_file)
        
        if args.verbose:
            print(f"Loaded palette with {len(palette)} colors")
        
        # Create the PNG
        create_png_from_indexed_data(
            decompressed_data, 
            palette, 
            args.width, 
            args.height, 
            args.output_file
        )
        
        print("Conversion completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
