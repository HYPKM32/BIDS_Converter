#!/usr/bin/env python3
"""
Canonical Reorientation CLI
Reorients NIfTI images to specified orientation (RAS, LPS, etc.)
"""

import argparse
import os
import sys
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from model.reorienter import Reorienter


def generate_output_filename(input_path, suffix='oriented'):
    """
    Generate output filename with format: {prefix}_drv-{suffix}_{original_suffix}.nii.gz
    If drv-* already exists, replace it with drv-{suffix}
    
    Args:
        input_path: Input file path
        suffix: Suffix name for drv- tag (default: 'oriented')
    
    Returns:
        Output filename
    
    Examples:
        # Case 1: No drv-* (add drv-oriented_)
        input:  'sub-2cna00001_ses-01_run-01_T1w.nii.gz'
        output: 'sub-2cna00001_ses-01_run-01_drv-oriented_T1w.nii.gz'
        
        # Case 2: Has drv-* (replace with drv-oriented)
        input:  'sub-2cna00001_ses-01_run-01_drv-original_T1w.nii.gz'
        output: 'sub-2cna00001_ses-01_run-01_drv-oriented_T1w.nii.gz'
    """
    basename = os.path.basename(input_path)
    
    # Determine extension
    if basename.endswith('.nii.gz'):
        extension = '.nii.gz'
        base_without_ext = basename[:-7]  # Remove .nii.gz
    elif basename.endswith('.nii'):
        extension = '.nii'
        base_without_ext = basename[:-4]  # Remove .nii
    else:
        extension = ''
        base_without_ext = basename
    
    # Split by underscore
    parts = base_without_ext.split('_')
    
    # Check if drv-* already exists
    has_drv = False
    new_parts = []
    
    for part in parts:
        if part.startswith('drv-'):
            # Replace existing drv-* with drv-{suffix}
            new_parts.append(f'drv-{suffix}')
            has_drv = True
        else:
            new_parts.append(part)
    
    # If no drv-* found, insert drv-{suffix} before last part
    if not has_drv:
        if len(new_parts) > 1:
            # Insert drv-{suffix} before the last suffix
            new_parts = new_parts[:-1] + [f'drv-{suffix}', new_parts[-1]]
        else:
            # Only one part, just append
            new_parts.append(f'drv-{suffix}')
    
    new_filename = '_'.join(new_parts) + extension
    return new_filename


def validate_inputs(args):
    """Validate input arguments."""
    # Check if input file exists
    if not os.path.isfile(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")
    
    # Check if input is NIfTI file
    if not (args.input.endswith('.nii') or args.input.endswith('.nii.gz')):
        raise ValueError("Input file must be a NIfTI file (.nii or .nii.gz)")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Validate axis orientation
    valid_orientations = ['RAS', 'LAS', 'LPS', 'RPS', 'RAI', 'LAI', 'LPI', 'RPI',
                         'ARS', 'ALS', 'PRS', 'PLS', 'ARI', 'ALI', 'PRI', 'PLI',
                         'SAR', 'SAL', 'SPR', 'SPL', 'IAR', 'IAL', 'IPR', 'IPL',
                         'SRA', 'SLA', 'SRP', 'SLP', 'IRA', 'ILA', 'IRP', 'ILP']
    
    if args.axis.upper() not in valid_orientations:
        print(f"Warning: '{args.axis}' may not be a standard orientation code.")
        print(f"Common orientations: RAS, LAS, LPS, LPI, etc.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Reorient NIfTI images to specified orientation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with RAS orientation (default)
  python canonical_cli.py -i input.nii.gz -o output_dir/
  
  # Specify LPS orientation
  python canonical_cli.py -i input.nii.gz -o output_dir/ -a LPS
  
  # Custom suffix
  python canonical_cli.py -i input.nii.gz -o output_dir/ -s reoriented
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input NIfTI file path (.nii or .nii.gz)'
    )
    
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output directory path (results will be saved here)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--axis', '-a',
        default='RAS',
        help='Target orientation (e.g., RAS, LPS, LPI, LAS). Default: RAS'
    )
    
    parser.add_argument(
        '--suffix', '-s',
        default='canonical',
        help='Suffix for drv- tag in output filename. Default: oriented'
    )
    
    args = parser.parse_args()
    
    try:
        # Validate inputs
        print("Validating inputs...")
        validate_inputs(args)
        
        # Generate output filename
        output_filename = generate_output_filename(args.input, args.suffix)
        output_path = os.path.join(args.output, output_filename)
        
        print(f"\nInput file:  {args.input}")
        print(f"Output file: {output_path}")
        print(f"Orientation: {args.axis}")
        print(f"Suffix:      {args.suffix}")
        print("\nStarting reorientation...\n")
        
        # Perform reorientation
        reorienter = Reorienter(orientation=args.axis.upper())
        result_path = reorienter.reorient(args.input, output_path)
        
        print(f"\n✓ Success! Reoriented file saved to:")
        print(f"  {result_path}")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())