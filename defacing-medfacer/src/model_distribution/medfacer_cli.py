#!/usr/bin/env python
# coding: utf-8
# /BDSP/medfacer_app/src/model_distribution/medfacer_cli.py
"""
MedFacer CLI - Command line interface for MRI defacing using 3D YOLO detection
"""

import argparse
import os
import sys
import re
import shutil
import subprocess
from pathlib import Path

from defacing.detect import run as yolo_detect
from defacing.masking import convert_and_create_mask
from defacing.inverting_and_operation import process_nifti_files as create_final_mask
from defacing.defacing import delete_masked_region


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = str(SCRIPT_DIR / "weight" / "best.pt")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='MedFacer - MRI Defacing Tool using 3D YOLO Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deface all face parts
  python3 medfacer_cli.py --input /data/nifti/ --output /data/output/

  # Deface only eyes and nose
  python3 medfacer_cli.py --input /data/nifti/ --output /data/output/ --parts eyes nose

  # Custom detection thresholds, dilation, and GPU
  python3 medfacer_cli.py --input /data/nifti/ --output /data/output/ --gpu 2 --conf 0.2 --dilate 15 --suffix anonymized
        """
    )

    # Required arguments
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input directory containing NIfTI files (.nii.gz)'
    )

    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output directory path (results will be saved here)'
    )

    # Optional arguments - GPU
    parser.add_argument(
        '--gpu', '-g',
        default='0',
        help='CUDA_VISIBLE_DEVICES index (default: 0)'
    )

    # Optional arguments - YOLO detection
    parser.add_argument(
        '--weights', '-w',
        default=None,
        help='Path to YOLO .pt weights (default: model/weights/best.pt)'
    )

    parser.add_argument(
        '--imgsz',
        type=int, default=256,
        help='YOLO input cube size (default: 256)'
    )

    parser.add_argument(
        '--conf',
        type=float, default=0.1,
        help='YOLO confidence threshold (default: 0.1)'
    )

    parser.add_argument(
        '--iou',
        type=float, default=0.1,
        help='YOLO NMS IoU threshold (default: 0.1)'
    )

    parser.add_argument(
        '--norm',
        default='MR', choices=['MR', 'CT', 'Other'],
        help='Intensity normalization mode (default: MR)'
    )

    # Optional arguments - face parts
    parser.add_argument(
        '--parts', '-p',
        nargs='+',
        choices=['eyes', 'nose', 'ears', 'mouth', 'all'],
        default=['all'],
        help='Face parts to deface (default: all). Can specify multiple: --parts eyes nose'
    )

    # Optional arguments - masking scales
    parser.add_argument(
        '--scale_eye',
        nargs=3, type=float, default=[1.5, 1.0, 1.0],
        help='Bbox scale [x, y, z] for eyes (default: 1.5 1.0 1.0)'
    )

    parser.add_argument(
        '--scale_ear',
        nargs=3, type=float, default=[1.0, 1.5, 1.5],
        help='Bbox scale [x, y, z] for ears (default: 1.0 1.5 1.5)'
    )

    parser.add_argument(
        '--scale_nose',
        nargs=3, type=float, default=[1.0, 1.0, 1.1],
        help='Bbox scale [x, y, z] for nose (default: 1.0 1.0 1.1)'
    )

    parser.add_argument(
        '--scale_mouth',
        nargs=3, type=float, default=[1.2, 1.2, 1.0],
        help='Bbox scale [x, y, z] for mouth (default: 1.2 1.2 1.0)'
    )

    # Optional arguments - DeepBET / brain mask
    parser.add_argument(
        '--dilate',
        type=int, default=10,
        help='Dilation iterations for brain mask inversion (default: 10)'
    )

    # Optional arguments - output control
    parser.add_argument(
        '--suffix', '-s',
        default='defacing',
        help='Suffix to append to output filename (default: defacing)'
    )

    parser.add_argument(
        '--mask', '-m',
        choices=['y', 'n'],
        default='y',
        help='Save segmentation mask (default: y)'
    )

    return parser.parse_args()


def parts_to_classes(parts):
    """
    Convert part names to YOLO class indices

    Args:
        parts: List of part names ['eyes', 'nose', 'ears', 'mouth'] or ['all']

    Returns:
        Sorted list of YOLO class indices
    """
    if 'all' in parts:
        return [0, 1, 2, 3, 4, 5]

    classes = []
    if 'eyes' in parts:
        classes.extend([0, 1])   # eye_left, eye_right
    if 'ears' in parts:
        classes.extend([2, 3])   # ear_left, ear_right
    if 'nose' in parts:
        classes.append(4)
    if 'mouth' in parts:
        classes.append(5)

    return sorted(classes)


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


def build_scale_map(args):
    """
    Build class-index to scale-factor mapping from arguments

    Returns:
        Dict mapping YOLO class index -> [scale_x, scale_y, scale_z]
    """
    return {
        0: args.scale_eye,    # eye_left
        1: args.scale_eye,    # eye_right
        2: args.scale_ear,    # ear_left
        3: args.scale_ear,    # ear_right
        4: args.scale_nose,   # nose
        5: args.scale_mouth,  # mouth
    }


def generate_output_filename(input_path, suffix):
    """
    Generate output filename with format: {prefix}_drv-{suffix}_{original_suffix}.nii.gz
    If drv-* already exists, replace it with drv-{suffix}

    Args:
        input_path: Input file path
        suffix: Suffix to add after 'drv-'

    Returns:
        Output filename

    Examples:
        # Case 1: No drv-* (add drv-{suffix}_)
        input:  'sub-2cna00001_ses-01_run-01_T1w.nii.gz', suffix='defaced'
        output: 'sub-2cna00001_ses-01_run-01_drv-defaced_T1w.nii.gz'

        # Case 2: Has drv-* (replace with drv-{suffix})
        input:  'sub-2cna00001_ses-01_run-01_drv-original_T1w.nii.gz', suffix='anonymized'
        output: 'sub-2cna00001_ses-01_run-01_drv-anonymized_T1w.nii.gz'
    """
    basename = os.path.basename(input_path)

    # Determine extension
    if basename.endswith('.nii.gz'):
        extension = '.nii.gz'
        base_without_ext = basename[:-7]
    elif basename.endswith('.nii'):
        extension = '.nii'
        base_without_ext = basename[:-4]
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
            new_parts.append(f'drv-{suffix}')
            has_drv = True
        else:
            new_parts.append(part)

    # If no drv-* found, insert drv-{suffix}_ before last part
    if not has_drv:
        if len(new_parts) > 1:
            new_parts = new_parts[:-1] + [f'drv-{suffix}', new_parts[-1]]
        else:
            new_parts.append(f'drv-{suffix}')

    new_filename = '_'.join(new_parts) + extension
    return new_filename


def generate_mask_filename(input_path):
    """
    Generate mask filename with format: {prefix}_defacemask.nii.gz

    Args:
        input_path: Input file path

    Returns:
        Mask filename

    Example:
        input: 'sub-2cna00001_ses-01_run-01_T1w.nii.gz'
        output: 'sub-2cna00001_ses-01_run-01_defacemask.nii.gz'
    """
    basename = os.path.basename(input_path)

    # Determine extension
    if basename.endswith('.nii.gz'):
        extension = '.nii.gz'
        base_without_ext = basename[:-7]
    elif basename.endswith('.nii'):
        extension = '.nii'
        base_without_ext = basename[:-4]
    else:
        extension = ''
        base_without_ext = basename

    pattern = r'^(.+_)([^_]+)$'
    match = re.match(pattern, base_without_ext)

    if match:
        prefix_part = match.group(1)
        mask_filename = f"{prefix_part}defacemask{extension}"
    else:
        mask_filename = f"{base_without_ext}_defacemask{extension}"

    return mask_filename


def validate_paths(args):
    """Validate input/output paths"""
    # Check input exists
    if not os.path.exists(args.input):
        print(f"Error: Input path does not exist: {args.input}")
        sys.exit(1)

    # Check if input is a directory
    if not os.path.isdir(args.input):
        print(f"Error: Input must be a directory containing NIfTI files")
        sys.exit(1)

    # Check for NIfTI files in input
    nifti_files = [f for f in os.listdir(args.input)
                   if f.endswith('.nii.gz') or f.endswith('.nii')]
    if not nifti_files:
        print(f"Error: No NIfTI files found in: {args.input}")
        sys.exit(1)

    # Check weights file if provided
    if args.weights and not os.path.isfile(args.weights):
        print(f"Error: Weights file not found: {args.weights}")
        sys.exit(1)

    # Create output directory if needed
    os.makedirs(args.output, exist_ok=True)

    return args


def main():
    """Main execution function"""
    # Parse arguments
    args = parse_arguments()

    # Validate paths
    args = validate_paths(args)

    # Set GPU before any CUDA operations
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    # Resolve paths
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)
    weights = args.weights or DEFAULT_WEIGHTS

    # Workspace for intermediate pipeline byproducts
    workspace_dir = str(SCRIPT_DIR / "workspace")

    # Intermediate directories under workspace
    detect_project = os.path.join(workspace_dir, 'yolo_detect')
    detect_name = 'exp_detect'
    label_dir = os.path.join(workspace_dir, 'labels')
    mask_dir = os.path.join(workspace_dir, 'masks')
    bet_brain_dir = os.path.join(workspace_dir, 'deepbet', 'brain')
    bet_mask_dir = os.path.join(workspace_dir, 'deepbet', 'mask')
    final_mask_dir = os.path.join(workspace_dir, 'final_masks')

    # Final output only
    defaced_dir = output_dir

    for d in [detect_project, label_dir, mask_dir,
              bet_brain_dir, bet_mask_dir, final_mask_dir, defaced_dir]:
        os.makedirs(d, exist_ok=True)

    # Convert parts to class indices and flags
    include_classes = parts_to_classes(args.parts)
    flags = parts_to_flags(args.parts)
    scale_map = build_scale_map(args)

    # YOLO labels directory (generated by detect)
    yolo_labels_dir = os.path.join(detect_project, detect_name, 'labels')

    # Print configuration
    print("=" * 60)
    print("MedFacer - MRI Defacing Tool (3D YOLO)")
    print("=" * 60)
    print(f"Input:        {input_dir}")
    print(f"Output Dir:   {output_dir}")
    print(f"Workspace:    {workspace_dir}")
    print(f"Weights:      {weights}")
    print(f"GPU:          {args.gpu}")
    print(f"Parts:        {args.parts}")
    print(f"  - Eyes:     {'Yes' if flags[0] else 'No'}")
    print(f"  - Nose:     {'Yes' if flags[1] else 'No'}")
    print(f"  - Ears:     {'Yes' if flags[2] else 'No'}")
    print(f"  - Mouth:    {'Yes' if flags[3] else 'No'}")
    print(f"Classes:      {include_classes}")
    print(f"Confidence:   {args.conf}")
    print(f"IoU:          {args.iou}")
    print(f"Norm:         {args.norm}")
    print(f"Dilate:       {args.dilate}")
    print(f"Suffix:       {args.suffix}")
    print("=" * 60)

    try:
        # Step 1: YOLO face-part detection
        print("\n[1/5] Running YOLO face-part detection...")
        yolo_detect(
            weights=weights,
            source=input_dir,
            imgsz=args.imgsz,
            conf_thres=args.conf,
            iou_thres=args.iou,
            norm=args.norm,
            save_txt=True,
            save_conf=True,
            project=detect_project,
            name=detect_name,
            exist_ok=True,
        )

        if not os.path.exists(yolo_labels_dir):
            print(f"Error: YOLO labels not generated at: {yolo_labels_dir}")
            return 1

        # Step 2: Generate 3D bounding-box masks from YOLO labels
        print("\n[2/5] Generating 3D bounding-box masks...")
        convert_and_create_mask(
            input_path=yolo_labels_dir,
            output_path=label_dir,
            nifti_src_dir=input_dir,
            mask_output_dir=mask_dir,
            scale_map=scale_map,
            include_classes=include_classes,
        )

        # Step 3: DeepBET brain extraction
        print("\n[3/5] Running DeepBET brain extraction...")
        subprocess.run(
            f"deepbet-cli -i {input_dir} -o {bet_brain_dir} -m {bet_mask_dir}",
            shell=True, check=True,
        )

        # Step 4: Invert brain mask + AND with YOLO mask
        print("\n[4/5] Creating brain-safe final mask (invert + AND)...")
        create_final_mask(
            bet_directory=bet_mask_dir,
            output_directory=final_mask_dir,
            reference_mask_dir=mask_dir,
            dilation_iterations=args.dilate,
        )

        # Step 5: Apply defacing
        print("\n[5/5] Applying defacing masks...")
        nifti_files = sorted([
            f for f in os.listdir(input_dir)
            if f.endswith('.nii.gz') or f.endswith('.nii')
        ])

        processed = 0
        for filename in nifti_files:
            input_path = os.path.join(input_dir, filename)

            # Resolve final mask path
            base = filename.replace('.nii.gz', '').replace('.nii', '')
            mask_name = base + '_final_mask.nii.gz'
            mask_path = os.path.join(final_mask_dir, mask_name)

            if not os.path.exists(mask_path):
                print(f"Warning: Mask not found for {filename}, skipping")
                continue

            # Generate BIDS-compatible output filename
            output_filename = generate_output_filename(filename, args.suffix)
            output_path = os.path.join(defaced_dir, output_filename)

            delete_masked_region(input_path, mask_path, output_path)

            # Save mask copy with standard naming
            if args.mask == 'y':
                mask_out_name = generate_mask_filename(filename)
                mask_out_path = os.path.join(defaced_dir, mask_out_name)
                shutil.copy2(mask_path, mask_out_path)

            processed += 1

        # Check result
        if processed > 0:
            print("\n" + "=" * 60)
            print("Defacing completed successfully!")
            print("=" * 60)
            print(f"Processed:    {processed} file(s)")
            print(f"YOLO labels:  {yolo_labels_dir}")
            print(f"Brain masks:  {bet_mask_dir}")
            print(f"Final masks:  {final_mask_dir}")
            print(f"Defaced:      {defaced_dir}")
            return 0
        else:
            print("\n" + "=" * 60)
            print("Defacing failed!")
            print("=" * 60)
            print("Error: No files were processed (masks not found)")
            return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print("An error occurred during processing!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
