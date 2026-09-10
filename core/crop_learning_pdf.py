"""Create the bundled Crop Learning & Manual Training Bot guide."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import mm
from pathlib import Path

def build_pdf(path):
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm)
    styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name="TitleCenter",parent=styles["Title"],alignment=TA_CENTER,fontSize=20,leading=24,spaceAfter=12)); styles.add(ParagraphStyle(name="Small",parent=styles["BodyText"],fontSize=9,leading=13,textColor=colors.HexColor("#555555")))
    story=[]
    story += [Paragraph("Passport Photo Studio Pro 3.4 — Advanced Detection & Crop Learning",styles["TitleCenter"]),Paragraph("Offline guide for Smart Tight Crop, Advanced Detection Ensemble, and Manual Crop Training Bot.",styles["BodyText"]),Spacer(1,8)]
    story += [Paragraph("1. What the advanced detector does",styles["Heading2"]),Paragraph("The detection engine combines frontal-face detection, eye cues, optional person detection, and upper-body/shoulder geometry. It produces composition geometry rather than identity recognition. The system is designed to keep processing local.",styles["BodyText"]),Spacer(1,6)]
    data=[["Signal","Purpose"],["Face box","Find face size and center"],["Eyes","Check frontal alignment"],["Person box (optional)","Cross-check subject extent"],["Shoulder geometry","Estimate useful lower framing"],["Composition score","Measure crop quality"]]
    t=Table(data,colWidths=[50*mm,115*mm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#30343b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#aaaaaa")),("VALIGN",(0,0),(-1,-1),"TOP"),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)])); story += [t,Spacer(1,10)]
    story += [Paragraph("2. Manual Crop Training Bot",styles["Heading2"]),Paragraph("When automatic framing is not ideal, open Manual Crop Trainer, drag a rectangle around the crop you consider correct, and save the example. Repeat with different photos. The bot stores normalized composition measurements: face height as a percentage of crop height, top margin, horizontal face position, and lower face-to-crop extent.",styles["BodyText"]),Spacer(1,5),Paragraph("Recommended workflow: 5 examples = basic personalization; 10–20 = stronger consistency; 20+ = useful for varied camera distances. Use different lighting, clothing, and backgrounds. Do not use training images to store or infer a person's identity.",styles["BodyText"]),Spacer(1,10)]
    story += [Paragraph("3. Training and applying",styles["Heading2"]),Paragraph("Save the learned profile as a JSON file. Future Smart Crop operations can use that profile as a composition preference. The learner is example-based and deterministic; it is not neural-network fine-tuning. This makes it lightweight and offline-friendly for older Windows PCs.",styles["BodyText"]),Spacer(1,10)]
    story += [Paragraph("4. Troubleshooting",styles["Heading2"]),Paragraph("If no face is detected, improve lighting, use a more frontal photo, or use the manual crop fallback. If the subject is too close to an image edge, the engine cannot invent missing pixels. If a crop repeatedly feels too tight or loose, add several corrected examples to the training set instead of relying on one image.",styles["BodyText"]),Spacer(1,10)]
    story += [Paragraph("5. Bangladesh 38×48 mm example",styles["Heading2"]),Paragraph("At 300 DPI, 38×48 mm is approximately 449×567 pixels. The physical output size and crop composition are separate: the crop bot chooses the composition, then the export engine resizes it to the exact pixel dimensions and embeds the requested DPI metadata.",styles["BodyText"]),Spacer(1,10)]
    story += [Paragraph("Important",styles["Heading2"]),Paragraph("Passport/visa authorities can have requirements beyond a generic photo size, including head-size ranges, background rules, glasses rules, and expression/pose rules. Treat the software's score as an editing aid, not an official eligibility guarantee.",styles["Small"])]
    doc.build(story)

if __name__=="__main__":
    build_pdf(Path(__file__).resolve().parents[1]/"docs"/"CROP_LEARNING_GUIDE.pdf")
