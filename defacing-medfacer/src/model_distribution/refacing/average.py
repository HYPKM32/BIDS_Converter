import os
import argparse
import numpy as np
import nibabel as nib
from scipy.ndimage import shift, zoom

# --------- Core I/O & geometry utils (unchanged) ---------
def load_nifti(path):
    img = nib.load(path)
    return img.get_fdata(), img.affine, img.header

def bbox_coords(volume):
    """Return bbox (z1,z2,x1,x2,y1,y2) for nonzero region; None if empty."""
    coords = np.argwhere(volume > 0)
    if coords.size == 0:
        return None
    z1, x1, y1 = coords.min(axis=0)
    z2, x2, y2 = coords.max(axis=0) + 1
    return (int(z1), int(z2), int(x1), int(x2), int(y1), int(y2))

def bbox_center_and_shape(volume):
    """Return center (z,x,y) and shape (dz,dx,dy) of nonzero bbox."""
    bb = bbox_coords(volume)
    if bb is None:
        return None, None
    z1, z2, x1, x2, y1, y2 = bb
    center = np.array([(z1 + z2) / 2.0, (x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=float)
    shape = (z2 - z1, x2 - x1, y2 - y1)
    return center, shape

def center_to(volume, target_center):
    """Shift volume so its nonzero-bbox center becomes target_center."""
    if np.sum(volume) == 0:
        return None
    cur_center, _ = bbox_center_and_shape(volume)
    if cur_center is None:
        return None
    shift_vec = np.array(target_center) - cur_center  # (z,x,y)
    return shift(volume, shift=shift_vec, order=1, mode='constant', cval=0)

def pad_or_crop_to(arr, target_shape):
    """Pad/crop to target_shape around the center."""
    pad_widths = []
    for cur, tgt in zip(arr.shape, target_shape):
        total_pad = max(0, tgt - cur)
        pad_before = total_pad // 2
        pad_after = total_pad - pad_before
        pad_widths.append((pad_before, pad_after))
    padded = np.pad(arr, pad_widths, mode='constant')
    zt, xt, yt = target_shape
    return padded[:zt, :xt, :yt]

def resize_to(arr, target_shape, order=1):
    """Linear (order=1) resize to target_shape."""
    if arr.size == 0:
        return arr
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if np.allclose(factors, 1.0):
        return arr
    return zoom(arr, factors, order=order)

def center_and_resize_to_shape(volume, target_shape):
    """Center-align to target center, then resize (and final pad/crop) to target_shape."""
    if np.sum(volume) == 0:
        return None
    target_center = np.array(target_shape, dtype=float) / 2.0
    shifted = center_to(volume, target_center)
    if shifted is None:
        return None
    if shifted.shape != tuple(target_shape):
        resized = resize_to(shifted, target_shape, order=1)
        return pad_or_crop_to(resized, target_shape)
    return shifted

def masked_mean(stack):
    """Mean ignoring zeros."""
    nonzero_mask = stack > 0
    num = np.sum(stack, axis=0)
    den = np.maximum(np.sum(nonzero_mask, axis=0), 1)
    return num / den

def load_all_volumes(input_dir):
    vols, names, affine, header = [], [], None, None
    if not os.path.isdir(input_dir):
        return vols, names, affine, header
    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith('.nii.gz'):
            continue
        path = os.path.join(input_dir, fname)
        data, affine, header = load_nifti(path)
        base = os.path.splitext(os.path.splitext(fname)[0])[0]
        vols.append(data)
        names.append(base)
    return vols, names, affine, header

# --------- Single-part averaging (original behavior) ---------
def build_per_target_averages(input_dir, output_dir, label):
    os.makedirs(output_dir, exist_ok=True)
    volumes, names, affine, header = load_all_volumes(input_dir)
    if not volumes:
        print(f"❌ No volumes found in {input_dir}.")
        return

    part_name = f"label{label}"

    for tgt_vol, sid in zip(volumes, names):
        tgt_center, tgt_shape = bbox_center_and_shape(tgt_vol)
        if tgt_shape is None or any(s <= 0 for s in tgt_shape):
            print(f"⚠️ Skipped target (empty or invalid bbox): {sid}")
            continue

        processed = []
        for src_vol in volumes:
            p = center_and_resize_to_shape(src_vol, tgt_shape)
            if p is not None:
                processed.append(p)

        if not processed:
            print(f"⚠️ No valid contributors for target {sid}")
            continue

        avg = masked_mean(np.stack(processed, axis=0))
        out_path = os.path.join(output_dir, f"average_{part_name}__like_{sid}.nii.gz")
        nib.save(nib.Nifti1Image(avg, affine, header), out_path)
        print(f"✅ Saved: {out_path} (shape={avg.shape}, sum={avg.sum():.2f})")

# --------- Multi-part batch mode (new) ---------
# Default mapping kept identical to your label indices
DEFAULT_PARTS = [
    ("eye_left", 0),
    ("eye_right", 1),
    ("ear_left", 2),
    ("ear_right", 3),
    ("nose", 4),
    ("mouth", 5),
]

def build_all_per_target_averages(input_root, output_root, parts=None):
    """
    Batch mode: iterate parts under input_root and write to output_root/<part>.
    'parts' can be a list of part names to restrict processing.
    """
    # Resolve mapping and selection
    part_map = dict(DEFAULT_PARTS)
    if parts:
        selected = [(p, part_map[p]) for p in parts if p in part_map]
    else:
        selected = DEFAULT_PARTS

    if not selected:
        print("❌ No valid parts to process.")
        return

    for part, label in selected:
        in_dir = os.path.join(input_root, part)
        out_dir = os.path.join(output_root, part)
        print(f"\n🧩 Per-target averaging | part={part} | label={label}")
        build_per_target_averages(in_dir, out_dir, label)

# --------- CLI ---------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Per-target averages (single part or batch over parts)")
    mode = parser.add_mutually_exclusive_group(required=True)

    # Original single-part mode (backward compatible)
    mode.add_argument('--input_dir', help='Dir with NIfTI parts (one label)')
    parser.add_argument('--output_dir', help='Dir to save results (single-part mode)')
    parser.add_argument('--label', type=int, help='Label index (e.g., 4 for nose)')

    # New batch mode over multiple parts
    mode.add_argument('--input_root', help='Root dir containing subdirs per part (e.g., landmarks/)')
    parser.add_argument('--output_root', help='Root dir to save per-part outputs (e.g., average/)')
    parser.add_argument(
        '--parts', nargs='*',
        help='Subset of parts to process (default: all). Choices: eye_left eye_right ear_left ear_right nose mouth'
    )

    args = parser.parse_args()

    # Dispatch
    if args.input_dir:
        if args.output_dir is None or args.label is None:
            raise SystemExit("For single-part mode, provide --input_dir, --output_dir, and --label.")
        print(f"🧩 Per-target averaging | label={args.label}")
        build_per_target_averages(args.input_dir, args.output_dir, args.label)
    else:
        if args.output_root is None:
            raise SystemExit("For batch mode, provide --input_root and --output_root.")
        build_all_per_target_averages(args.input_root, args.output_root, parts=args.parts)