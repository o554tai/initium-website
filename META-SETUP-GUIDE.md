# Meta (Facebook/Instagram) Pixel Setup — Step by Step

## What You Need
- A Facebook account (personal is fine)
- Your ACRA BizFile (for business verification)
- ~10 minutes

---

## Step 1: Create Meta Business Manager

1. Go to **https://business.facebook.com**
2. Click **"Create Account"**
3. Enter:
   - **Business Name:** INITIUM
   - **Your Name:** (your name)
   - **Business Email:** tassocpc@gmail.com
4. Click **Submit**

---

## Step 2: Add Your Facebook Page

1. In Business Manager, click the **9-dot menu** (☰) → **Accounts** → **Pages**
2. Click **"Add Page"** → **"Add a Page"**
3. Enter your INITIUM Facebook page name/URL
4. Click **Add Page**

---

## Step 3: Verify Your Business (Required for Ads)

1. In Business Manager, go to **Business Settings** → **Security Center** → **Business Verification**
2. Click **Start Verification**
3. Select verification method:
   - **Recommended:** Upload ACRA BizFile PDF
   - Alternative: Phone/email verification
4. Enter business details:
   - **Legal Name:** (as per ACRA)
   - **Address:** (registered address)
   - **Phone:** +65 8846 4814
5. Upload documents → wait for approval (usually 24–48 hours)

---

## Step 4: Create Ad Account

1. Go to **Business Settings** → **Accounts** → **Ad Accounts**
2. Click **"Add Ad Account"** → **"Create a New Ad Account"**
3. Name it: **INITIUM Lead Gen**
4. Currency: **SGD**
5. Time Zone: **Singapore**
6. Click **Create**

---

## Step 5: Create & Copy Your Pixel ID

1. Go to **Events Manager**: https://business.facebook.com/events_manager
2. Click **"Connect Data Sources"**
3. Select **Web**
4. Name: **INITIUM Website**
5. Enter domain: **initium.sg**
6. Click **Create**
7. Meta shows a 15-digit number like: `123456789012345`
8. **Copy this number** — this is your Pixel ID

---

## Step 6: Paste It Into INITIUM

Send me the Pixel ID (just the 15-digit number).

I will run one command and every page on initium.sg will be updated instantly.

---

## Step 7: Verify Installation

1. Install **Meta Pixel Helper** Chrome extension
   - https://chrome.google.com/webstore/detail/meta-pixel-helper/fdgfkebogiimcoedlicjlajpkdmockpc
2. Visit **https://initium.sg**
3. The extension icon should show a **green checkmark** ✓ with your Pixel ID
4. Visit **https://initium.sg/new-launch-landing.html**
5. Submit the form → extension should show a **"Lead"** event fired

---

## Step 8: Launch Your First Campaign (S$10/day test)

### Campaign Settings
- **Objective:** Leads
- **Campaign Name:** INITIUM Test — Thomson Reserve

### Ad Set Settings
- **Budget:** S$10/day
- **Audience:**
  - Location: Singapore
  - Age: 25–55
  - Interests: PropertyGuru, 99.co, Real Estate, New Launch Condo, Investment Property
- **Placements:** Automatic (Meta optimizes)
- **Optimization:** Leads

### Ad Creative
- **Format:** Single Image or Carousel
- **Headline:** Thomson Reserve | VVIP Preview Access
- **Primary Text:**
  > District 20. Upper Thomson. 180 exclusive units.
  > INITIUM clients get first access — before the public.
  > Tap to register. No obligation.
- **Call-to-Action:** Learn More (links to landing page)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Business verification pending" | Wait 24–48h, or re-upload clearer BizFile |
| Pixel Helper shows "No Pixel Found" | Check if ad blocker is blocking Facebook scripts |
| Form submit but no Lead event | Hard refresh (Cmd+Shift+R on Mac) |
| Ad account disabled | Appeal via Account Quality page; usually auto-approval for legit businesses |
