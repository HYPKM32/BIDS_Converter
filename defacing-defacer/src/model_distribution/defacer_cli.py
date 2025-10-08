#!/usr/bin/env python
# coding: utf-8
# /BDSP/defacer_app/src/model_distribution/defacer_cli.py
"""
Defacer CLI - Command line interface for medical image de-identification
"""

import argparse
import os
import sys
import re
from model.defacer import Defacer


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Defacer - Medical Image De-identification Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # De-identify all face parts
  python3 defacer_cli.py --input image.nii.gz --output /path/to/output/
  
  # De-identify only eyes and nose with custom suffix
  python3 defacer_cli.py --input image.nii.gz --output /path/to/output/ --parts eyes nose --suffix anonymized
  
  # De-identify without verification image
  python3 defacer_cli.py --input image.nii.gz --output /path/to/output/ --verification n
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
        '--parts', '-p',
        nargs='+',
        choices=['eyes', 'nose', 'ears', 'mouth', 'all'],
        default=['all'],
        help='Face parts to de-identify (default: all). Can specify multiple: --parts eyes nose'
    )
    
    parser.add_argument(
        '--suffix', '-s',
        default='defaced',
        help='Suffix to append to output filename (default: defaced). Example: T1w becomes T1w-defaced'
    )
    
    parser.add_argument(
        '--verification', '-v',
        choices=['y', 'n'],
        default='y',
        help='Generate verification image (default: y)'
    )
    
    parser.add_argument(
        '--mask', '-m',
        choices=['y', 'n'],
        default='y',
        help='Save segmentation mask (default: y)'
    )
    
    parser.add_argument(
        '--url',
        default='',
        help='Base URL for file access (optional)'
    )
    
    return parser.parse_args()


def parts_to_flags(parts):
    """
    Convert part names to boolean flags
    
    Args:
        parts: List of part names ['eyes', 'nose', 'ears', 'mouth'] or ['all']
    
    Returns:
        Tuple of (eyes, nose, ears, mouth) as boolean flags
    """
    if 'all' in parts:
        return (1, 1, 1, 1)
    
    flags = [
        1 if 'eyes' in parts else 0,
        1 if 'nose' in parts else 0,
        1 if 'ears' in parts else 0,
        1 if 'mouth' in parts else 0
    ]
    
    return tuple(flags)


def generate_output_filename(input_path, suffix):
    """
    Generate output filename by adding suffix to the original suffix
    
    Args:
        input_path: Input file path
        suffix: Suffix to add (e.g., 'defaced')
    
    Returns:
        Output filename
    
    Example:
        input: 'sub-2cna00001_ses-01_run-01_T1w.nii.gz'
        suffix: 'defaced'
        output: 'sub-2cna00001_ses-01_run-01_T1w-defaced.nii.gz'
    """
    basename = os.path.basename(input_path)
    
    # Match pattern: filename ending with underscore + original_suffix + .nii or .nii.gz
    pattern = r'^(.+_)([^_]+)(\.nii(?:\.gz)?)$'
    match = re.match(pattern, basename)
    
    if match:
        prefix_part = match.group(1)  # Everything up to and including last underscore
        original_suffix = match.group(2)  # Original suffix (e.g., 'T1w')
        extension = match.group(3)  # .nii or .nii.gz
        
        new_filename = f"{prefix_part}{original_suffix}-{suffix}{extension}"
    else:
        # Fallback: if pattern doesn't match, just add suffix before extension
        if basename.endswith('.nii.gz'):
            new_filename = basename.replace('.nii.gz', f'-{suffix}.nii.gz')
        elif basename.endswith('.nii'):
            new_filename = basename.replace('.nii', f'-{suffix}.nii')
        else:
            new_filename = f"{basename}-{suffix}"
    
    return new_filename


def generate_mask_filename(input_path):
    """
    Generate mask filename by replacing the last suffix with 'defacing-mask'
    
    Args:
        input_path: Input file path
    
    Returns:
        Mask filename
    
    Example:
        input: 'sub-sub-2cna00001Hanyangparknm_ses-01_run-01_T1w.nii.gz'
        output: 'sub-sub-2cna00001Hanyangparknm_ses-01_run-01_defacing-mask.nii.gz'
    """
    basename = os.path.basename(input_path)
    
    # Match pattern: filename ending with underscore + original_suffix + .nii or .nii.gz
    pattern = r'^(.+_)([^_]+)(\.nii(?:\.gz)?)$'
    match = re.match(pattern, basename)
    
    if match:
        prefix_part = match.group(1)  # Everything up to and including last underscore
        extension = match.group(3)  # .nii or .nii.gz
        
        mask_filename = f"{prefix_part}defacing-mask{extension}"
    else:
        # Fallback: if pattern doesn't match, just add mask before extension
        if basename.endswith('.nii.gz'):
            mask_filename = basename.replace('.nii.gz', '_defacing-mask.nii.gz')
        elif basename.endswith('.nii'):
            mask_filename = basename.replace('.nii', '_defacing-mask.nii')
        else:
            mask_filename = f"{basename}_defacing-mask"
    
    return mask_filename


def generate_verification_filename(output_filename):
    """
    Generate verification image filename by replacing .nii/.nii.gz with .png
    
    Args:
        output_filename: Output NIfTI filename
    
    Returns:
        Verification PNG filename
    
    Example:
        input: 'sub-2cna00001_ses-01_run-01_T1w-defaced.nii.gz'
        output: 'sub-2cna00001_ses-01_run-01_T1w-defaced.png'
    """
    if output_filename.endswith('.nii.gz'):
        return output_filename.replace('.nii.gz', '.png')
    elif output_filename.endswith('.nii'):
        return output_filename.replace('.nii', '.png')
    else:
        return output_filename + '.png'


def validate_paths(args):
    """Validate input/output paths"""
    # Check input exists
    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}")
        sys.exit(1)
    
    # Check if input is a file
    if not os.path.isfile(args.input):
        print(f"Error: Input must be a NIfTI file (.nii or .nii.gz)")
        sys.exit(1)
    
    # Validate NIfTI file extension
    valid_extensions = ['.nii', '.nii.gz']
    if not any(args.input.endswith(ext) for ext in valid_extensions):
        print(f"Warning: Input file may not be a valid NIfTI file")
    
    # Create output directory if needed
    if not os.path.exists(args.output):
        os.makedirs(args.output, exist_ok=True)
    
    # Check if output is a directory
    if not os.path.isdir(args.output):
        print(f"Error: Output must be a directory path")
        sys.exit(1)
    
    return args


def main():
    """Main execution function"""
    # Parse arguments
    args = parse_arguments()
    
    # Validate paths
    args = validate_paths(args)
    
    # Convert parts to flags
    where = parts_to_flags(args.parts)
    
    # Generate output filename
    output_filename = generate_output_filename(args.input, args.suffix)
    output_path = os.path.join(args.output, output_filename)
    
    # Generate mask filename (always saved)
    mask_filename = generate_mask_filename(args.input)
    mask_path = os.path.join(args.output, mask_filename)
    
    # Set verification path
    if args.verification == 'y':
        verif_filename = generate_verification_filename(output_filename)
        verif_path = os.path.join(args.output, verif_filename)
    else:
        verif_path = None
    
    # Print configuration
    print("=" * 60)
    print("Defacer - Medical Image De-identification (NIfTI)")
    print("=" * 60)
    print(f"Input:        {args.input}")
    print(f"Output Dir:   {args.output}")
    print(f"Output File:  {output_filename}")
    print(f"Mask File:    {mask_filename}")
    print(f"Parts:        {args.parts}")
    print(f"  - Eyes:     {'Yes' if where[0] else 'No'}")
    print(f"  - Nose:     {'Yes' if where[1] else 'No'}")
    print(f"  - Ears:     {'Yes' if where[2] else 'No'}")
    print(f"  - Mouth:    {'Yes' if where[3] else 'No'}")
    print(f"Suffix:       {args.suffix}")
    if args.verification == 'y':
        print(f"Verification: {verif_filename}")
    else:
        print(f"Verification: Disabled")
    print("=" * 60)
    
    # Initialize Defacer
    print("\nInitializing Defacer...")
    defacer = Defacer()
    
    # Process NIfTI file
    print(f"\nProcessing NIfTI file...")
    
    try:
        result = defacer.Deidentification_image_nii(
            where=where,
            nfti_path=args.input,
            dest_path=output_path,
            mask_path=mask_path,
            verif_path=verif_path,
            url=args.url,
            prefix=''  # Not used anymore, but kept for compatibility
        )
        
        # Check result
        if result['success']:
            print("\n" + "=" * 60)
            print("✓ De-identification completed successfully!")
            print("=" * 60)
            print(f"Output saved to: {output_path}")
            print(f"Mask saved to: {mask_path}")
            if args.verification == 'y':
                print(f"Verification image: {verif_path}")
            if result.get('files'):
                print(f"Processed {len(result['files'])} file(s)")
            return 0
        else:
            print("\n" + "=" * 60)
            print("✗ De-identification failed!")
            print("=" * 60)
            print(f"Error: {result.get('msg', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ An error occurred during processing!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())