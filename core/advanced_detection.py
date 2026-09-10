"""Advanced offline passport-photo detection ensemble.

Uses multiple OpenCV detectors and geometry heuristics. No cloud service and no
identity recognition. The output is composition geometry only.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import cv2
import numpy as np

# Low-end PC defaults: avoid OpenCV thread oversubscription and GPU/OpenCL overhead.
try:
    cv2.setNumThreads(1)
    cv2.setUseOptimized(True)
    cv2.ocl.setUseOpenCL(False)
except Exception:
    pass
from PIL import Image

@dataclass
class DetectionResult:
    face: tuple[int,int,int,int] | None
    eyes: list[tuple[int,int,int,int]]
    person: tuple[int,int,int,int] | None
    shoulder_box: tuple[int,int,int,int] | None
    confidence: float
    method: str
    notes: list[str]

    def to_dict(self):
        return asdict(self)

def _cascade(name):
    candidates=[]
    meipass=getattr(sys,"_MEIPASS",None)
    if meipass:
        candidates.append(Path(meipass)/"assets"/"cascades"/name)
    candidates.append(Path(__file__).resolve().parents[1]/"assets"/"cascades"/name)
    try:
        candidates.append(Path(cv2.data.haarcascades)/name)
    except Exception: pass
    for p in candidates:
        if p.is_file():
            c=cv2.CascadeClassifier(str(p))
            if not c.empty(): return c
    return None

def _largest_face(gray):
    c=_cascade("haarcascade_frontalface_default.xml")
    if c is None: return None
    # LOW-END OPTIMIZATION: detection runs on a small working image only.
    h,w=gray.shape[:2]
    max_dim=900
    scale=min(1.0, max_dim/max(h,w))
    work=gray if scale>=.999 else cv2.resize(gray,(max(1,int(w*scale)),max(1,int(h*scale))),interpolation=cv2.INTER_AREA)
    wh,ww=work.shape[:2]
    boxes=c.detectMultiScale(work,1.08,4,minSize=(max(24,int(min(ww,wh)*.035)),)*2)
    if not len(boxes): return None
    bx,by,bw,bh=max(boxes,key=lambda b:b[2]*b[3])
    if scale < .999:
        inv=1.0/scale
        bx,by,bw,bh=[int(round(v*inv)) for v in (bx,by,bw,bh)]
    return (int(bx),int(by),int(bw),int(bh))

def _eyes(gray, face):
    if not face: return []
    c=_cascade("haarcascade_eye_tree_eyeglasses.xml") or _cascade("haarcascade_eye.xml")
    if c is None: return []
    x,y,w,h=face
    roi=gray[y:y+int(h*.62),x:x+w]
    if roi.size==0: return []
    # Eyes are cheap because the ROI is already small.
    boxes=c.detectMultiScale(roi,1.08,4,minSize=(max(8,int(w*.07)),max(7,int(h*.05))))
    return [(int(x+bx),int(y+by),int(bw),int(bh)) for bx,by,bw,bh in boxes[:4]]

def _person_hog(rgb):
    # Disabled by default: OpenCV HOG is extremely CPU-heavy on low-end PCs.
    # It can be enabled explicitly with PPS_ENABLE_HOG=1.
    import os
    if os.getenv("PPS_ENABLE_HOG", "0") != "1":
        return None
    try:
        h,w=rgb.shape[:2]; scale=min(1.0,640/max(h,w))
        work=rgb if scale>=.999 else cv2.resize(rgb,(max(1,int(w*scale)),max(1,int(h*scale))),interpolation=cv2.INTER_AREA)
        hog=cv2.HOGDescriptor(); hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        b,_=hog.detectMultiScale(cv2.cvtColor(work,cv2.COLOR_RGB2BGR),winStride=(16,16),padding=(8,8),scale=1.08)
        if len(b):
            q=max(b,key=lambda z:z[2]*z[3]); inv=1/scale
            return tuple(int(round(v*inv)) for v in q)
    except Exception:
        pass
    return None

def _shoulders(face, iw, ih, person=None):
    if not face: return None
    x,y,w,h=face
    cx=x+w/2
    if person:
        px,py,pw,ph=person
        left=max(0,int(px)); right=min(iw,int(px+pw))
        top=max(0,int(y+h*.70)); bottom=min(ih,int(y+h*3.0))
        if right-left >= w*1.2:
            return (left,top,right-left,max(1,bottom-top))
    sw=int(min(iw*.86,w*3.0))
    left=max(0,int(cx-sw/2)); top=max(0,int(y+h*.72)); bottom=min(ih,int(y+h*2.75))
    return (left,top,max(1,sw),max(1,bottom-top))

def detect_advanced(img: Image.Image, use_hog: bool | None = None) -> DetectionResult:
    rgb=np.asarray(img.convert("RGB"))
    # Keep the full image in memory, but use a compact grayscale copy for detection.
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    gray=cv2.createCLAHE(1.5,(8,8)).apply(gray)
    face=_largest_face(gray)
    eyes=_eyes(gray,face)
    if use_hog is None:
        import os
        use_hog = os.getenv("PPS_ENABLE_HOG", "0") == "1"
    person=_person_hog(rgb) if (face is not None and use_hog) else None
    shoulder=_shoulders(face,rgb.shape[1],rgb.shape[0],person)
    notes=[]
    conf=0.0
    if face:
        conf += .62
        notes.append("frontal face geometry detected")
    if len(eyes)>=2:
        conf += .16
        notes.append("paired eyes detected")
    elif len(eyes)==1:
        conf += .05
        notes.append("single eye cue detected")
    if person:
        conf += .12
        notes.append("person detector agrees with subject region")
    if shoulder:
        conf += .10
        notes.append("shoulder/upper-body region estimated")
    conf=min(1.0,conf)
    method="ensemble" if person else "face+geometry"
    return DetectionResult(face,eyes,person,shoulder,conf,method,notes)
