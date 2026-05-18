# INITIUM 3D Virtual Tour — Build Workflow

> Internal guide for capturing, processing, and publishing Gaussian Splatting property tours.

---

## Overview

| | |
|---|---|
| **Technology** | Gaussian Splatting (3D Gaussian Radiance Fields) |
| **Output** | Browser-based walkthrough, no app required |
| **File size** | 30–80 MB per 4-bedroom unit |
| **Cost** | $0–$150 per scan |
| **Turnaround** | Same day |

---

## Step 1: Capture

### Equipment Options

| Tier | Gear | Cost | Best For |
|---|---|---|---|
| **Free** | iPhone 13+ (Pro/Pro Max preferred) | $0 | Quick scans, resale units |
| **Budget** | iPhone 15 Pro + Polaroid Cube tripod | $50 | Consistent framing |
| **Pro** | DJI RS3 Mini gimbal + iPhone 15 Pro | $400 | Showflats, developer pitches |

### Capture Rules (Non-Negotiable)

1. **Lighting**: Overcast afternoon or evenly lit interiors. No direct sun patches.
2. **Speed**: Walk 1 step per second. No running.
3. **Coverage**: Capture chest height AND knee height per room. Cover every corner.
4. **Stability**: Keep phone at consistent height (1.2m for HDB, 1.4m for condos).
5. **No motion**: Turn off fans, close curtains, remove pets, ask occupants to step out.
6. **Plan the path**: Walk dry first, then scan. Avoid backtracking through same space.

### Recommended Apps

| App | Platform | Cost | Note |
|---|---|---|---|
| **Polycam** | iOS / Android | Free (watermark) / $8/mo | Easiest UI, fastest export |
| **Luma AI** | iOS | Free | Best free quality, good reflections |
| **Postshot** | Desktop (Windows/Mac) | Free beta | Pro control, manual alignment |

### Quick Start (Polycam)

1. Open Polycam → Select "Room" mode
2. Tap record → Walk slowly through the unit
3. Cover every room twice (different angles)
4. Stop recording → Upload for processing (2–5 min)
5. Export as `.ply` or `.splat`

---

## Step 2: Clean & Compress (SuperSplat)

SuperSplat is a free browser-based editor. No install required.

**URL**: https://playcanvas.com/super-splat

### Workflow

1. **Upload** your `.ply` or `.splat` file
2. **Crop**: Remove outside geometry (sky, neighbouring units, cars)
3. **Delete floaters**: Use rectangle select to remove stray splats
4. **Simplify**: Reduce to 300k–500k splats for mobile performance
5. **Export**: `File → Export → .splat` or publish directly to PlayCanvas

### Target Settings

| Device Target | Splats | File Size | FPS |
|---|---|---|---|
| Flagship mobile | 500k | 60–80 MB | 30–60 |
| Mid-range mobile | 300k | 30–50 MB | 25–40 |
| Desktop only | 1M+ | 100+ MB | 60+ |

---

## Step 3: Publish

### Option A: PlayCanvas (Recommended)

1. Go to https://playcanvas.com
2. Create free account → New Project → Blank
3. Upload your `.splat` file to Assets
4. Add to scene → Position camera start point
5. Publish → Get public URL
6. Embed URL in `virtual-tours.html` via iframe:

```html
<iframe src="https://playcanvas.com/project/XXXX/embed"
        width="100%" height="500" frameborder="0"
        allow="xr-spatial-tracking" loading="lazy">
</iframe>
```

### Option B: Self-Host (Advanced)

Use `splat` viewer from https://github.com/antimatter15/splat

1. Host `.splat` file on GitHub Pages / CDN
2. Embed viewer pointing to file URL
3. Full control, no platform lock-in

---

## Step 4: Embed on initium.sg

### Add Tour to Gallery

Edit `virtual-tours.html`:

```html
<div class="tour-card">
  <div class="tour-preview">
    <iframe src="YOUR_PLAYCANVAS_URL" loading="lazy"
            allow="xr-spatial-tracking"></iframe>
    <div class="tour-badge">New Launch</div>
  </div>
  <div class="tour-info">
    <div class="tour-name">Project Name</div>
    <div class="tour-loc">Location, District</div>
    <div class="tour-meta">
      <span>📱 Mobile</span>
      <span>🎥 3D</span>
      <span>⚡ XX MB</span>
    </div>
    <a href="FULLSCREEN_URL" class="tour-btn" target="_blank">Enter Tour</a>
  </div>
</div>
```

### Add "3D Tour" Badge to New-Launches Cards

In `new-launches.html`, add a small badge:

```html
<div class="property-badge" style="background:var(--ig);color:#fff;">3D Tour →</div>
```

---

## Pricing Strategy

### Internal Use (Recommended Phase 1)

| Service | Price | Target |
|---|---|---|
| Free 3D tour | $0 | Listings above $1.5M |
| Free 3D tour | $0 | Exclusive new launches |
| Free 3D tour | $0 | Team recruitment showflats |

### Revenue Service (Phase 2)

| Service | Price | Target |
|---|---|---|
| Developer showflat scan | $500–$800 | Boutique developers |
| Resale listing scan | $300–$500 | Individual sellers |
| Rental portfolio scan | $200–$300/unit | Landlords with 3+ units |
| Hotel / Airbnb scan | $400–$600 | Boutique hospitality |

---

## Competitive Positioning

| vs. | Our Edge |
|---|---|
| **Matterport** | 10× cheaper, no subscription, mobile-native |
| **Video walkthrough** | Interactive, not linear. Buyer controls the path. |
| **360° photos** | True depth perception. Reflections and glass look real. |
| **Other agents** | First-mover advantage in Singapore at this scale. |

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Smudged / blurry areas | Not enough angles captured | Re-scan with slower walk, more overlap |
| Floating debris in air | Glass reflections captured as objects | Delete in SuperSplat rectangle tool |
| File too large for mobile | Too many splats | Simplify to 300k in SuperSplat |
| Black holes when looking around | Missing camera coverage | Ensure 360° coverage per room |
| iPhone gets hot | Long capture session | Take breaks, close other apps |

---

## Checklist Before First Client Scan

- [ ] Practice scan your own office (Great World City)
- [ ] Process in SuperSplat, publish to PlayCanvas
- [ ] Test on iPhone, Android, and laptop
- [ ] Verify load time under 5 seconds on 4G
- [ ] Add tour to `virtual-tours.html`
- [ ] Send test link to 3 team members for feedback
- [ ] Document best angles for typical Singapore layouts

---

**Questions?** WhatsApp Hermes or the tech lead.
