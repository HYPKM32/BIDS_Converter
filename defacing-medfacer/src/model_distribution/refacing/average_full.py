#!/usr/bin/env python3
"""
Average full-face NIfTI volumes in a folder into a single mean volume.

Features:
- Loads all .nii or .nii.gz files in a directory.
- Optionally resamples every volume to the reference grid (first file) using linear interpolation.
- Optional per-volume intensity normalization (none | zscore | percentile).
- Optionally average only over voxels that are nonzero in each volume (mask_nonzero).
- Saves the mean as float32 NIfTI using the reference affine/header.

Example:
python average_face.py \
  --input_dir /nasdata3/defacing/parent_directory/images/train \
  --out /nasdata3/defacing/parent_directory/images/train_mean_face.nii.gz \
  --align \
  --intensity_norm percentile --p_low 2 --p_high 98 \
  --mask_nonzero
"""

import os
import sys
import glob
import argparse
import numpy as np
import nibabel as nib

try:
    from nibabel.processing import resample_from_to
except Exception:
    resample_from_to = None

def parse_args():
    p = argparse.ArgumentParser(description="Average NIfTI volumes in a folder.")
    p.add_argument("--input_dir", type=str, required=True,
                   help="Folder containing .nii or .nii.gz files.")
    p.add_argument("--out", type=str, required=True,
                   help="Output path for averaged NIfTI (e.g., mean_face.nii.gz).")
    p.add_argument("--align", action="store_true",
                   help="Resample all volumes to match the reference grid (first file).")
    p.add_argument("--intensity_norm", type=str, default="none",
                   choices=["none", "zscore", "percentile"],
                   help="Per-volume intensity normalization mode.")
    p.add_argument("--p_low", type=float, default=2.0,
                   help="Lower percentile for 'percentile' normalization.")
    p.add_argument("--p_high", type=float, default=98.0,
                   help="Upper percentile for 'percentile' normalization.")
    p.add_argument("--mask_nonzero", action="store_true",
                   help="Average only over voxels that are nonzero in each volume.")
    return p.parse_args()

def normalize_volume(vol, mode="none", p_low=2.0, p_high=98.0):
    """Apply per-volume intensity normalization."""
    vol = vol.astype(np.float32, copy=False)
    if mode == "none":
        return vol
    if mode == "zscore":
        m = np.mean(vol)
        s = np.std(vol)
        if s > 0:
            vol = (vol - m) / s
        else:
            vol = vol * 0.0
        return vol
    if mode == "percentile":
        lo = np.percentile(vol, p_low)
        hi = np.percentile(vol, p_high)
        if hi > lo:
            vol = np.clip(vol, lo, hi)
            vol = (vol - lo) / (hi - lo)  # scale to [0,1]
        else:
            vol = vol * 0.0
        return vol
    return vol

def main():
    args = parse_args()

    # Collect files
    files = sorted(glob.glob(os.path.join(args.input_dir, "*.nii"))) + \
            sorted(glob.glob(os.path.join(args.input_dir, "*.nii.gz")))
    if not files:
        print(f"❌ No NIfTI files found in: {args.input_dir}")
        sys.exit(1)

    # Load reference (first file)
    ref_img = nib.load(files[0])
    ref_shape = ref_img.shape
    ref_affine = ref_img.affine
    ref_header = ref_img.header.copy()

    if args.align and resample_from_to is None:
        print("⚠️ 'align' requested but nibabel.processing.resample_from_to not available. Proceeding without alignment.")
        args.align = False

    # Prepare accumulators
    running_sum = np.zeros(ref_shape, dtype=np.float64)
    if args.mask_nonzero:
        running_count = np.zeros(ref_shape, dtype=np.uint32)
    else:
        running_count = None

    used_files = []

    for idx, f in enumerate(files, 1):
        try:
            img = nib.load(f)
        except Exception as e:
            print(f"⚠️ Skip (cannot load): {f} ({e})")
            continue

        vol_img = img
        if args.align:
            # Resample to reference grid (same shape/affine). Linear interpolation (order=1)
            try:
                vol_img = resample_from_to(img, ref_img, order=1)
            except Exception as e:
                print(f"⚠️ Skip (resample failed): {f} ({e})")
                continue
        else:
            # If not aligning, ensure shapes match
            if vol_img.shape != ref_shape:
                print(f"⚠️ Skip (shape mismatch without --align): {f} {vol_img.shape} != {ref_shape}")
                continue

        vol = vol_img.get_fdata(dtype=np.float32)

        # Per-volume normalization
        vol = normalize_volume(vol, mode=args.intensity_norm, p_low=args.p_low, p_high=args.p_high)

        if args.mask_nonzero:
            nz = vol != 0
            running_sum[nz] += vol[nz].astype(np.float64, copy=False)
            running_count[nz] += 1
        else:
            running_sum += vol.astype(np.float64, copy=False)

        used_files.append(f)
        if idx % 10 == 0:
            print(f"… processed {idx} / {len(files)}")

    if not used_files:
        print("❌ No volumes processed successfully. Exiting.")
        sys.exit(1)

    # Compute mean
    if args.mask_nonzero:
        with np.errstate(divide="ignore", invalid="ignore"):
            mean_vol = np.zeros(ref_shape, dtype=np.float32)
            valid = running_count > 0
            mean_vol[valid] = (running_sum[valid] / running_count[valid]).astype(np.float32)
            # voxels never observed (count==0) remain 0
    else:
        mean_vol = (running_sum / float(len(used_files))).astype(np.float32)

    # Save output
    out_img = nib.Nifti1Image(mean_vol, ref_affine, ref_header)
    nib.save(out_img, args.out)

    print(f"✅ Saved mean face volume: {args.out}")
    print(f"ℹ️ Used {len(used_files)} files (first used as reference):")
    for f in used_files[:5]:
        print(f"   - {f}")
    if len(used_files) > 5:
        print(f"   … and {len(used_files) - 5} more")

if __name__ == "__main__":
    main()
