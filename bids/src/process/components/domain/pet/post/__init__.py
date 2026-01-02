# PET Post 모듈
# - bids_checker: PET 전용 (data_type='pet', modality='pet' 고정)
# - byproduct, thumbnail: MRI 모듈 재사용

from process.components.domain.pet.post import bids_checker  # PET 전용
from process.components.domain.mri.post import byproduct     # MRI 재사용
from process.components.domain.mri.post import thumbnail     # MRI 재사용

__all__ = ['bids_checker', 'byproduct', 'thumbnail']
