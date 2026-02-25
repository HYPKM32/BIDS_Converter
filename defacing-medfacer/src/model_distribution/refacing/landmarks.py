import os
import nibabel as nib
import numpy as np
import argparse

# 클래스 번호와 이름 매핑
CLASS_NAMES = {
    1: 'eye_left',
    2: 'eye_right',
    3: 'ear_left',
    4: 'ear_right',
    5: 'nose',
    6: 'mouth'
}

def extract_parts(mask_dir, image_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for fname in os.listdir(mask_dir):
        if not fname.endswith('_mask.nii.gz'):
            continue

        mask_path = os.path.join(mask_dir, fname)
        if fname.endswith('_final_mask.nii.gz'):
            base_name = fname.replace('_final_mask.nii.gz', '.nii.gz')
        else:
            base_name = fname.replace('_mask.nii.gz', '.nii.gz')
        
        image_path = os.path.join(image_dir, base_name)

        if not os.path.exists(image_path):
            print(f"⚠️ Original image not found: {image_path}")
            continue

        # Load mask and image
        mask_img = nib.load(mask_path)
        mask_data = mask_img.get_fdata()
        affine = mask_img.affine
        header = mask_img.header

        image_img = nib.load(image_path)
        image_data = image_img.get_fdata()

        for class_val, part_name in CLASS_NAMES.items():
            # 해당 클래스의 마스크 추출
            part_mask = (mask_data == class_val)
            if np.sum(part_mask) == 0:
                print(f"❌ {part_name} not found in {fname}")
                continue

            # 원본 영상에서 해당 영역만 추출
            part_volume = np.zeros_like(image_data)
            part_volume[part_mask] = image_data[part_mask]

            # 부위별 폴더 생성
            part_folder = os.path.join(output_dir, part_name)
            os.makedirs(part_folder, exist_ok=True)

            # 저장
            out_fname = base_name.replace('.nii.gz', f'_{part_name}.nii.gz')
            out_path = os.path.join(part_folder, out_fname)
            nib.save(nib.Nifti1Image(part_volume, affine, header), out_path)
            print(f"✅ Saved: {out_path}")

    print("🎉 All parts extracted and saved in class-wise folders.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mask_dir', required=True, help='Directory containing *_mask.nii.gz files')
    parser.add_argument('--image_dir', required=True, help='Directory containing original NIfTI images')
    parser.add_argument('--output_dir', required=True, help='Directory to save extracted parts')
    args = parser.parse_args()

    extract_parts(args.mask_dir, args.image_dir, args.output_dir)
