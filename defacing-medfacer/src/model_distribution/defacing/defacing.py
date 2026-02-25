import os
import nibabel as nib
import numpy as np
import argparse

def delete_masked_region(input_mri_path, mask_path, output_path):
    """
    마스크된 영역을 삭제 (값을 0으로 설정)
    """
    mri_nii = nib.load(input_mri_path)
    mri_data = mri_nii.get_fdata()

    mask_nii = nib.load(mask_path)
    mask_data = mask_nii.get_fdata()

    mask_data = mask_data.astype(np.int32)
    mri_data[mask_data > 0] = 0

    modified_mri_nii = nib.Nifti1Image(mri_data, mri_nii.affine, mri_nii.header)
    nib.save(modified_mri_nii, output_path)
    print(f"Defaced MRI saved: {output_path}")

def process_mask_deletion(input_directory, mask_directory, output_directory):
    """
    디렉토리 내 모든 MRI 파일에 대해 마스크된 영역을 삭제
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for filename in os.listdir(input_directory):
        if filename.endswith('.nii.gz'):
            input_mri_path = os.path.join(input_directory, filename)
            mask_path = os.path.join(mask_directory, filename.replace('.nii.gz', '_final_mask.nii.gz'))
            output_path = os.path.join(output_directory, filename.replace('.nii.gz', '_defaced.nii.gz'))

            if not os.path.exists(mask_path):
                print(f"⚠️ 마스크 파일이 없습니다: {mask_path}")
                continue

            delete_masked_region(input_mri_path, mask_path, output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mri_dir', required=True, help='원본 MRI 파일들이 있는 디렉토리')
    parser.add_argument('--mask_dir', required=True, help='마스크(.nii.gz) 파일들이 있는 디렉토리')
    parser.add_argument('--output_dir', required=True, help='defaced MRI를 저장할 디렉토리')

    args = parser.parse_args()
    process_mask_deletion(args.mri_dir, args.mask_dir, args.output_dir)
