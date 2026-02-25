import os
import glob
import argparse
import numpy as np
import nibabel as nib
from scipy.ndimage import zoom


def load_nifti(path):
    """Load NIfTI file and return (data, affine, header)."""
    img = nib.load(path)
    return img.get_fdata(), img.affine, img.header


def resolve_part_path(avg_root: str, part_key: str):
    # 1) avg_root/average/part.nii.gz
    p1 = os.path.join(avg_root, "average", f"{part_key}.nii.gz")
    if os.path.isfile(p1):
        return p1

    # 2) avg_root/average_part.nii.gz
    p2 = os.path.join(avg_root, f"average_{part_key}.nii.gz")
    if os.path.isfile(p2):
        return p2

    # 3) avg_root/part.nii.gz
    p3 = os.path.join(avg_root, f"{part_key}.nii.gz")
    if os.path.isfile(p3):
        return p3

    # 4) avg_root/part/*.nii.gz (take the first)
    p4_dir = os.path.join(avg_root, part_key)
    if os.path.isdir(p4_dir):
        cand = sorted(glob.glob(os.path.join(p4_dir, "*.nii.gz")))
        if len(cand) > 0:
            return cand[0]

    return None


def insert_parts_with_dirs(mask_path, avg_root, output_dir, label_to_part):
    """
    For each label in the mask, find the corresponding average part from avg_root,
    resize it to the bounding box of that label, and insert only non-zero voxels.
    """
    mask_data, affine, header = load_nifti(mask_path)
    insert_data = np.zeros_like(mask_data, dtype=np.float32)

    for label_val, part_key in label_to_part.items():
        part_path = resolve_part_path(avg_root, part_key)
        if not part_path:
            print(f"❌ Part not found for '{part_key}' (label {label_val}). "
                  f"Checked under: {avg_root}/average/, average_{part_key}.nii.gz, {part_key}.nii.gz, {part_key}/")
            continue

        avg_part, _, _ = load_nifti(part_path)

        # locate the mask region (bounding box) for this label
        mask_coords = np.argwhere(mask_data == label_val)
        if mask_coords.size == 0:
            print(f"❌ No voxels for label {label_val} in mask: {os.path.basename(mask_path)}")
            continue

        z1, x1, y1 = mask_coords.min(axis=0)
        z2, x2, y2 = mask_coords.max(axis=0) + 1
        dz, dx, dy = z2 - z1, x2 - x1, y2 - y1
        if dz <= 0 or dx <= 0 or dy <= 0:
            print(f"❌ Invalid bbox for label {label_val} in {os.path.basename(mask_path)}")
            continue

        # crop non-zero region from average part
        part_coords = np.argwhere(avg_part > 0)
        if part_coords.size == 0:
            print(f"❌ No non-zero voxels in part '{part_key}' ({os.path.basename(part_path)})")
            continue

        pz1, px1, py1 = part_coords.min(axis=0)
        pz2, px2, py2 = part_coords.max(axis=0) + 1
        cropped_part = avg_part[pz1:pz2, px1:px2, py1:py2]

        # resize (trilinear) to bbox size
        zoom_factors = (
            dz / max(cropped_part.shape[0], 1),
            dx / max(cropped_part.shape[1], 1),
            dy / max(cropped_part.shape[2], 1)
        )
        resized_part = zoom(cropped_part, zoom_factors, order=1)

        # insert only where (mask==label) AND resized_part>0
        region_mask = (mask_data[z1:z2, x1:x2, y1:y2] == label_val)
        non_zero_mask = resized_part > 0
        insert_mask = region_mask & non_zero_mask

        # write into output volume
        region = insert_data[z1:z2, x1:x2, y1:y2]
        region[insert_mask] = resized_part[insert_mask]
        insert_data[z1:z2, x1:x2, y1:y2] = region

        print(f"✅ Inserted '{part_key}' (label {label_val}) from {os.path.basename(part_path)} "
              f"into bbox z[{z1}:{z2}] x[{x1}:{x2}] y[{y1}:{y2}]")

    os.makedirs(output_dir, exist_ok=True)
    out_name = os.path.basename(mask_path).replace("_mask", "_inserted")
    out_path = os.path.join(output_dir, out_name)
    nib.save(nib.Nifti1Image(insert_data, affine, header), out_path)
    print(f"🎯 Saved inserted volume: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Insert facial average parts into label masks.")
    parser.add_argument("--mask_dir", required=True, help="Directory with *_mask.nii.gz files")
    parser.add_argument("--avg_root", required=True,
                        help="Root directory containing average parts in flexible structure "
                             "(e.g., average/part.nii.gz, average_part.nii.gz, part.nii.gz, or part/*.nii.gz)")
    parser.add_argument("--output_dir", required=True, help="Output directory for inserted volumes")
    args = parser.parse_args()

    # Label → part key mapping (edit if your labels differ)
    label_to_part = {
        1: "eye_left",
        2: "eye_right",
        3: "ear_left",
        4: "ear_right",
        5: "nose",
        6: "mouth",
    }

    mask_files = [f for f in os.listdir(args.mask_dir) if f.endswith("_mask.nii.gz")]
    if not mask_files:
        print(f"❌ No mask files found in {args.mask_dir}")
        return

    for fn in sorted(mask_files):
        mask_path = os.path.join(args.mask_dir, fn)
        insert_parts_with_dirs(mask_path, args.avg_root, args.output_dir, label_to_part)


if __name__ == "__main__":
    main()
