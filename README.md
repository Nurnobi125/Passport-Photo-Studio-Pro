# Passport Photo Studio Pro v5.0.0 📸

[![Release](https://img.shields.io/badge/release-v5.0.0-blue.svg)](https://github.com/your-username/PassportPhotoStudioPro/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4.svg)](https://microsoft.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Privacy](https://img.shields.io/badge/privacy-Local%20Processing-brightgreen.svg)](#data--privacy)

> **Professional Passport, Visa, and ID Photo Creation Suite for Windows 10 & 11**

**Passport Photo Studio Pro** is an AI-powered desktop application designed to streamline biometrics, passport crop training, background removal, and print layout preparation—optimized specifically for high performance on both standard and low-end PCs.

---

## 🌟 Key Features

* **Photoshop-Style Manual Crop Training:** Interact with an intuitive 8-handle crop box featuring aspect-ratio locking, precise zoom, and panning. Save custom compositions as local targets.
* **Train Once, Auto-Apply:** Train the intelligent bot once using face-anchored geometry to automatically format incoming photos across various image resolutions and subject distances.
* **Smart Background Removal:** Instant background replacement powered by local OpenCV processing with seamless fallback support.
* **Exact Standard Presets:** Pre-configured sizing specifications for official passports and visas (e.g., US, UK, EU, Bangladesh 35x45mm).
* **Print-Ready Layouts:** Prepare multi-photo grid layouts (including A4 sheets) with automated alignment and print preview features[cite: 1, 2].
* **Low-End PC Optimization:** Lightweight multithreading, compact working image detection, and optional HOG detection ensure smooth performance on low-spec hardware[cite: 1].
* **Privacy First:** All composition training and face-detection routines operate 100% locally on your machine[cite: 1].

---

## 🚀 Quick Start & Installation

### Prerequisites
- **OS:** Windows 10 or Windows 11 (64-bit)
- **Python:** 3.10+ (if running from source)

### Building Executable & MSIX Package

1. **Build Windows Executable:**
   ```bash
    pip main.py
