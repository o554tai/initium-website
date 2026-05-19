# Google Ads Conversion Tracking Setup — Step by Step

## What You Need
- A Google account
- A credit card (for billing, even for small budgets)
- ~10 minutes

---

## Step 1: Create Google Ads Account

1. Go to **https://ads.google.com**
2. Click **"Start now"**
3. Sign in with your Google account
4. When asked about campaign goal, select **"Create an account without a campaign"**
   - (We'll build campaigns after tracking is set up)
5. Enter billing country: **Singapore**
6. Currency: **SGD**
7. Time zone: **Singapore**
8. Submit billing info (required even for small spends)

---

## Step 2: Create a Conversion Action

1. In Google Ads, click the **wrench icon** (🔧) → **Conversions** (under "Measurement")
2. Click **"New conversion action"**
3. Select **Website**
4. Enter domain: **initium.sg**
5. Click **Scan**
6. Click **"Add a conversion action manually"**
7. Configure:
   - **Category:** Submit lead form
   - **Name:** INITIUM Lead Form Submit
   - **Value:** Don't use a value for this conversion action
   - **Count:** One
   - **Click-through conversion window:** 30 days
   - **Engaged-view conversion window:** 3 days
   - **Attribution model:** Data-driven
8. Click **Create and continue**

---

## Step 3: Get Your Conversion ID + Label

After creating the conversion action, Google shows you the **tag setup** screen.

**Option A: Copy the full tag (I'll extract the values)**

Google shows code like this:
```html
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-XXXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'AW-XXXXXXXXXXX');
</script>
```

And a separate event snippet:
```html
<script>
  gtag('event', 'conversion', {
      'send_to': 'AW-XXXXXXXXXXX/YYYYYYYYYYYYYYY',
      'value': 1.0,
      'currency': 'SGD'
  });
</script>
```

**What you need to copy:**
1. **Conversion ID**: The `AW-XXXXXXXXXXX` part (looks like `AW-12345678901`)
2. **Conversion Label**: The `YYYYYYYYYYYYYYY` part after the slash (looks like `abcDeF1gHiJk2LmN`)

Just send me both values. I'll update everything.

---

## Step 4: Verify Installation

1. Install **Tag Assistant (Legacy)** Chrome extension
   - https://chrome.google.com/webstore/detail/tag-assistant-by-google/kejbdjndbnbjgmefkgdddjlbokphdefk
2. Visit **https://initium.sg/new-launch-landing.html**
3. Enable Tag Assistant → it should show your Google Ads tag loaded
4. Submit the form → it should show the conversion event fired

---

## Step 5: Create Your First Campaign (S$5/day test)

### Campaign Type
- **Search campaign** (people actively searching for property)

### Settings
- **Campaign name:** INITIUM Test — New Launch Singapore
- **Networks:** Search Network only (uncheck Display Network)
- **Locations:** Singapore
- **Languages:** English
- **Budget:** S$5/day
- **Bidding:** Maximize conversions

### Keywords (start with these)
```
new launch condo singapore
condo launch 2026
property agent singapore
buy condo singapore
new launch district 20
thomson reserve
vvip preview condo
```

### Ad Groups
- **Ad Group 1:** New Launch General
- **Ad Group 2:** Thomson Reserve Specific

### Ad Copy Example
**Headline 1:** New Launch Condos Singapore
**Headline 2:** VVIP Preview Access
**Headline 3:** No Buyer Agent Fee
**Description:** Register with INITIUM for first access to new launches. Floor plans & pricing before public release. 70+ agents islandwide.
**Final URL:** https://initium.sg/new-launch-landing.html

---

## Important: Landing Page Policy

Google manually reviews real estate landing pages. Your page MUST have:
- ✅ Privacy Policy link
- ✅ Terms of Service link
- ✅ Real contact info (matches business registration)
- ✅ No "guaranteed returns" claims
- ✅ No false urgency ("only 2 units left" without proof)

Both are now live at:
- https://initium.sg/privacy-policy.html
- https://initium.sg/terms-of-service.html

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Account under review" | Normal for new accounts. Wait 24-48h. |
| Tag Assistant shows "No tags found" | Ad blocker blocking. Disable for initium.sg. |
| Conversion not tracking | Check that the event fires AFTER gtag is loaded. |
| High CPC (>$5) | Start with long-tail keywords like "new launch district 20 condo" |
| Low impressions | Increase bid or broaden keywords slightly. |

---

## Recommended Monthly Budget Split

| Platform | Daily | Monthly | Purpose |
|----------|-------|---------|---------|
| Meta (FB/IG) | S$10 | S$300 | Primary lead gen + retargeting |
| Google Ads | S$5 | S$150 | High-intent search traffic |
| **Total** | **S$15** | **S$450** | Test & validate |

Scale whichever gives lower cost per lead first.
