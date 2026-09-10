# Passport Photo Studio Pro v5.0.0

## Major upgrade
**Photoshop-style Manual Crop Training + Train Once + Auto Apply**

The Manual Train workspace now acts like a crop tool: move the crop rectangle, resize from eight handles, lock the passport aspect ratio, zoom and pan, and save the exact manual crop as the training target.

After **Train Bot**, the profile is saved locally and can be automatically applied to newly opened photos. The crop engine uses face-anchored geometry so different image resolutions and subject distances can share the learned composition.

### Low-end PC design
- Face detection uses a compact working image.
- OpenCV thread count is limited.
- OpenCL/GPU overhead is disabled by default.
- Heavy HOG person detection is optional and off by default.
- Smart crop runs in a background thread so the Tkinter UI remains responsive.

### Data/privacy
Training is local. The bot learns composition geometry, not identity. Images are not uploaded by the crop trainer.
