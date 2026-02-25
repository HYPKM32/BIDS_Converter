import os
import nibabel as nib
import numpy as np
import argparse

def load_nifti(path):
    img = nib.load(path)
    return img.get_fdata(), img.affine, img.header

def match_intensity_range(source, target):
    source_vals = source.flatten()
    target_vals = target.flatten()

    if np.ptp(source_vals) == 0 or np.ptp(target_vals) == 0:
        return target

    s_min, s_max = source_vals.min(), source_vals.max()
    t_min, t_max = target_vals.min(), target_vals.max()

    scaled = (target - t_min) / (t_max - t_min)
    matched = scaled * (s_max - s_min) + s_min
    return matched
    
def merge_defaced_and_inserted(defaced_path, inserted_path, output_path):
    defaced_data, affine, header = load_nifti(defaced_path)
    inserted_data, _, _ = load_nifti(inserted_path)

    if defaced_data.shape != inserted_data.shape:
        raise ValueError(f"Shape mismatch: defaced {defaced_data.shape}, inserted {inserted_data.shape}")

    mask = inserted_data > 1e-5
    inserted_data = match_intensity_range(defaced_data, inserted_data)

    merged_data = defaced_data.copy()
    merged_data[mask] = inserted_data[mask]

    os.makedirs(output_path, exist_ok=True)
    out_path = os.path.join(output_path, os.path.basename(defaced_path).replace("_defaced", "_refaced"))
    nib.save(nib.Nifti1Image(merged_data, affine, header), out_path)
    print(f"✅ Refaced image saved: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaced_dir", required=True)
    parser.add_argument("--inserted_dir", required=True)
    parser.add_argument("--output_path", required=True)
    args = parser.parse_args()

    defaced_files = [f for f in os.listdir(args.defaced_dir) if f.endswith("_defaced.nii.gz")]
    if not defaced_files:
        print("❌ No defaced images found.")
        exit(1)

    for f in defaced_files:
        inserted_name = f.replace("_defaced.nii.gz", "_final_inserted.nii.gz")
        defaced_path = os.path.join(args.defaced_dir, f)
        inserted_path = os.path.join(args.inserted_dir, inserted_name)

        if not os.path.exists(inserted_path):
            print(f"⚠️ No matching inserted file for: {f}")
            continue

        try:
            merge_defaced_and_inserted(defaced_path, inserted_path, args.output_path)
        except Exception as e:
            print(f"❌ Failed to process {f}: {e}")