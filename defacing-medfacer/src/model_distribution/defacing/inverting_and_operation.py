import os
import nibabel as nib
import numpy as np
from scipy.ndimage import binary_dilation
import argparse

def dilate_invert_mask(input_mask_path, output_mask_path, dilation_iterations=7):
    mask_nii = nib.load(input_mask_path)
    mask_data = mask_nii.get_fdata()

    mask_data = (mask_data > 0.5).astype(np.uint8)

    # dilation
    dilated_mask = binary_dilation(mask_data, iterations=dilation_iterations).astype(np.uint8)

    # 반전
    inverted_mask_data = np.logical_not(dilated_mask).astype(np.uint8)

    inverted_mask_nii = nib.Nifti1Image(inverted_mask_data, mask_nii.affine, mask_nii.header)
    nib.save(inverted_mask_nii, output_mask_path)
    print(f"✅ Inverted mask saved: {output_mask_path}")
    return output_mask_path

def create_intersection_mask(mask1_path, mask2_path, output_path):
    try:
        # Load both masks
        mask1_nii = nib.load(mask1_path)
        mask1_data = mask1_nii.get_fdata()
    except Exception as e:
        print(f"❌ Failed to load mask1: {mask1_path}\n{e}")
        return

    try:
        mask2_nii = nib.load(mask2_path)
        mask2_data = mask2_nii.get_fdata()
    except Exception as e:
        print(f"❌ Failed to load mask2: {mask2_path}\n{e}")
        return

    # Ensure mask2_data exists before this line
    intersection_data = np.where(mask1_data == 1, mask2_data, 0)

    intersection_nii = nib.Nifti1Image(intersection_data.astype(np.uint8), mask1_nii.affine, mask1_nii.header)
    nib.save(intersection_nii, output_path)
    print(f"✅ Final intersection mask saved: {output_path}")


def process_nifti_files(bet_directory, output_directory, reference_mask_dir, dilation_iterations):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for filename in os.listdir(bet_directory):
        if filename.endswith('.nii.gz') and '_inverted' not in filename and '_dilated' not in filename:
            bet_mask_path = os.path.join(bet_directory, filename)
            
            base_filename = filename.replace('.nii.gz', '')

            inverted_mask_path = os.path.join(bet_directory, filename.replace('.nii.gz', '_inverted.nii.gz'))
            
            reference_filename = filename.replace('.nii.gz', '_mask.nii.gz')
            reference_mask_path = os.path.join(reference_mask_dir, reference_filename)
            final_mask_path = os.path.join(output_directory, filename.replace('.nii.gz', '_final_mask.nii.gz'))

            inverted_mask_path = dilate_invert_mask(bet_mask_path, inverted_mask_path, dilation_iterations)

            if os.path.exists(reference_mask_path):
                create_intersection_mask(inverted_mask_path, reference_mask_path, final_mask_path)
            else:
                print(f"⚠️ Reference mask not found: {reference_mask_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--bet_dir', required=True, help='Directory containing _bet.nii.gz masks from HD-BET')
    parser.add_argument('--ref_mask_dir', required=True, help='Directory containing reference YOLO masks')
    parser.add_argument('--output_dir', required=True, help='Directory to save final intersection masks')
    parser.add_argument('--dilate', type=int, default=7, help='Number of iterations for binary dilation (default=7)')

    args = parser.parse_args()
    process_nifti_files(args.bet_dir, args.output_dir, args.ref_mask_dir, args.dilate)