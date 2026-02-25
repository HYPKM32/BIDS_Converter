import os
import nibabel as nib
import numpy as np
import math
import argparse

def convert_and_create_mask(input_path, output_path, nifti_src_dir, mask_output_dir, scale_map, include_classes):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    if not os.path.exists(mask_output_dir):
        os.makedirs(mask_output_dir)

    for filename in os.listdir(input_path):
        input_file_path = os.path.join(input_path, filename)
        if not os.path.isfile(input_file_path) or not filename.endswith('.txt'):
            continue

        base_filename = filename.replace('.txt', '.nii.gz')
        nifti_src_path = os.path.join(nifti_src_dir, base_filename)
        if not os.path.isfile(nifti_src_path):
            print(f"⚠️ NIfTI file {nifti_src_path} not found, skipping.")
            continue

        nifti_img = nib.load(nifti_src_path)
        img_dimensions = nifti_img.shape
        img_width, img_height, img_depth = img_dimensions
        affine = nifti_img.affine

        output_file_path = os.path.join(output_path, filename)
        mask_output_path = os.path.join(mask_output_dir, f"{filename.replace('.txt', '_mask.nii.gz')}")
        mask_array = np.zeros(img_dimensions, dtype=np.uint8)

        with open(input_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        original_format_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 7:
                print(f"Skipping malformed line in {filename}: {line.strip()}")
                continue

            parts = parts[:7]
            try:
                class_num = int(parts[0])
                if class_num not in include_classes:
                    continue

                z_center = float(parts[1]) * img_depth
                x_center = float(parts[2]) * img_width
                y_center = float(parts[3]) * img_height
                z_length = float(parts[4]) * img_depth
                x_length = float(parts[5]) * img_width
                y_length = float(parts[6]) * img_height
            except ValueError as e:
                print(f"Error processing line in {filename}: {line.strip()} -> {e}")
                continue

            # 클래스별 스케일
            scale_factors = scale_map.get(class_num, [1.0, 1.0, 1.0])
            x_length *= scale_factors[0]
            y_length *= scale_factors[1]
            z_length *= scale_factors[2]

            original_format_line = f"{class_num} {x_center:.1f} {y_center:.1f} {z_center:.1f} {x_length:.1f} {y_length:.1f} {z_length:.1f}\n"
            original_format_lines.append(original_format_line)

            min_x = max(0, int(math.floor(x_center - x_length / 2)))
            max_x = min(img_width, int(math.ceil(x_center + x_length / 2)))
            min_y = max(0, int(math.floor(y_center - y_length / 2)))
            max_y = min(img_height, int(math.ceil(y_center + y_length / 2)))
            min_z = max(0, int(math.floor(z_center - z_length / 2)))
            max_z = min(img_depth, int(math.ceil(z_center + z_length / 2)))

            mask_value = class_num + 1  # label 1~N (0 is background)
            mask_array[min_x:max_x, min_y:max_y, min_z:max_z] = mask_value

        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.writelines(original_format_lines)

        nifti_image = nib.Nifti1Image(mask_array, affine)
        nib.save(nifti_image, mask_output_path)
        print(f"✅ 3D mask saved: {mask_output_path}")

    print("🎉 All masks generated successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', required=True)
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--nifti_src_dir', required=True)
    parser.add_argument('--mask_out_dir', required=True)
    parser.add_argument('--include_classes', nargs='+', type=int, default=[0, 1, 2, 3, 4, 5])

    parser.add_argument('--scale_eye', nargs=3, type=float, default=[1.0, 1.0, 1.0])
    parser.add_argument('--scale_ear', nargs=3, type=float, default=[1.0, 1.0, 1.0])
    parser.add_argument('--scale_nose', nargs=3, type=float, default=[1.0, 1.0, 1.0])
    parser.add_argument('--scale_mouth', nargs=3, type=float, default=[1.0, 1.0, 1.0])

    args = parser.parse_args()

    scale_map = {
        0: args.scale_eye,   # left eye
        1: args.scale_eye,   # right eye
        2: args.scale_ear,   # left ear
        3: args.scale_ear,   # right ear
        4: args.scale_nose,  # nose
        5: args.scale_mouth  # mouth
    }

    convert_and_create_mask(
        args.input_dir,
        args.output_dir,
        args.nifti_src_dir,
        args.mask_out_dir,
        scale_map,
        args.include_classes
    )