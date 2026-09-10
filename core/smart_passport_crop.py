"""Advanced Smart Passport Crop engine.

Uses an offline detection ensemble and optional manual-training profile. It targets
head-and-shoulder composition, then resizes to exact physical output dimensions.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ImageDraw
from .advanced_detection import detect_advanced
from .manual_training_bot import apply_profile_to_geometry

@dataclass
class CropAnalysis:
    rect: tuple[int,int,int,int]
    face: tuple[int,int,int,int] | None
    score: int
    message: str
    face_ratio: float=0.0
    head_top_ratio: float=0.0
    center_offset_ratio: float=0.0
    crop_mode: str="advanced-ensemble"
    confidence: float=0.0
    eyes_detected: int=0
    person_detected: bool=False
    shoulder_box: tuple[int,int,int,int] | None=None
    training_applied: bool=False

def analyze_crop(img: Image.Image,width_mm:float,height_mm:float,training_profile=None)->CropAnalysis:
    rgb=np.asarray(img.convert("RGB")); ih,iw=rgb.shape[:2]; ratio=float(width_mm)/float(height_mm)
    det=detect_advanced(img); face=det.face
    if face is None:
        ch=min(ih,int(round(iw/ratio))); cw=min(iw,int(round(ch*ratio)))
        if cw<iw: ch=min(ih,int(round(cw/ratio)))
        l=(iw-cw)//2; t=max(0,(ih-ch)//2); rect=(l,t,l+cw,t+ch)
        return CropAnalysis(rect,None,35,"No face detected — centered fallback crop used.",crop_mode="fallback",confidence=0.0)
    x,y,fw,fh=face; cx=x+fw/2
    if training_profile and training_profile.get("examples",0)>0:
        rect=apply_profile_to_geometry(face,iw,ih,ratio,training_profile)
        mode="advanced+trained"
        trained=True
    else:
        # Ensemble-derived tight default. Head top ≈ 8.5%; face ≈ 36.5% of crop.
        target_face_ratio=.365 if ratio<.90 else .34
        crop_h=fh/target_face_ratio; crop_w=crop_h*ratio
        top=y-.085*crop_h
        bottom=y+2.25*fh
        if bottom>top+crop_h:
            crop_h=bottom-top; crop_w=crop_h*ratio
        # If the subject is near a source edge, fit while preserving ratio.
        crop_w=min(crop_w,iw*.96); crop_h=crop_w/ratio
        crop_h=min(crop_h,ih*.96); crop_w=crop_h*ratio
        left=cx-crop_w/2; top=max(0,min(ih-crop_h,top)); left=max(0,min(iw-crop_w,left))
        rect=(int(round(left)),int(round(top)),int(round(left+crop_w)),int(round(top+crop_h)))
        mode="advanced-ensemble"; trained=False
    l,t,r,b=rect; rw=max(1,r-l); rh=max(1,b-t)
    head_top=max(0,(y-t)/rh); face_ratio=fh/rh; center_off=abs((x+fw/2)-(l+rw/2))/rw
    # Composition score: face size, top margin, centering, detector confidence, bounds.
    target=.365 if ratio<.90 else .34
    score=100
    score-=min(28,abs(head_top-.085)*190)
    score-=min(28,abs(face_ratio-target)*150)
    score-=min(22,center_off*180)
    score+=min(8,det.confidence*8)
    if t<=1 or b>=ih-1: score-=4
    if det.eyes and len(det.eyes)>=2: score+=2
    score=int(max(1,min(100,round(score))))
    msg=("Excellent advanced head-and-shoulder framing." if score>=90 else
         "Good advanced framing; a small manual correction may improve it." if score>=75 else
         "Usable framing; source photo or subject distance limits crop room.")
    return CropAnalysis(rect,face,score,msg,face_ratio,head_top,center_off,mode,det.confidence,len(det.eyes),det.person is not None,det.shoulder_box,trained)

def smart_passport_crop(img,width_mm,height_mm,dpi=300,training_profile=None):
    analysis=analyze_crop(img,width_mm,height_mm,training_profile)
    l,t,r,b=analysis.rect
    crop=img.convert("RGB").crop((l,t,r,b))
    out_w=max(1,round(width_mm/25.4*dpi)); out_h=max(1,round(height_mm/25.4*dpi))
    out=crop.resize((out_w,out_h),Image.Resampling.LANCZOS); out.info["dpi"]=(dpi,dpi)
    return out,analysis

def draw_crop_guide(img,analysis,scale=1.0):
    out=img.convert("RGB").copy(); d=ImageDraw.Draw(out)
    l,t,r,b=analysis.rect
    d.rectangle((l,t,r,b),outline=(255,40,40),width=max(3,int(6*scale)))
    if analysis.face:
        x,y,w,h=analysis.face; d.rectangle((x,y,x+w,y+h),outline=(60,210,255),width=max(2,int(4*scale)))
    if analysis.shoulder_box:
        sx,sy,sw,sh=analysis.shoulder_box; d.rectangle((sx,sy,sx+sw,sy+sh),outline=(80,255,150),width=max(2,int(3*scale)))
    # Eye cue is represented by small guide markers when available through the detector.
    try:
        from .advanced_detection import detect_advanced
        det=detect_advanced(img)
        for ex,ey,ew,eh in det.eyes[:4]:
            d.ellipse((ex,ey,ex+ew,ey+eh),outline=(255,170,50),width=max(2,int(2*scale)))
    except Exception:
        pass
    gy=int(round(t+(b-t)*.085)); d.line((l,gy,r,gy),fill=(255,210,60),width=max(2,int(3*scale)))
    return out
