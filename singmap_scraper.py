#!/usr/bin/env python3
"""
SingMap scraper - logs into app.singmap.com and extracts project data.
Credentials provided by user.
Uses JavaScript injection for login to bypass UI interaction issues.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_FILE = Path("/home/hermes/initium-website/ecoprop_projects.json")
CACHE_FILE = Path("/home/hermes/ecoprop_projects.json")

async def fetch_from_singmap():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(f"[{datetime.now()}] Playwright not installed")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.new_page()

        try:
            # Navigate to login page
            print(f"[{datetime.now()}] Navigating to singmap login...")
            await page.goto('https://app.singmap.com/#/login', wait_until='commit', timeout=20000)
            await page.wait_for_timeout(8000)

            # Use JavaScript to fill form and submit
            print(f"[{datetime.now()}] Attempting login via JS...")
            login_result = await page.evaluate('''(credentials) => {
                return new Promise((resolve) => {
                    // Find all input fields
                    const inputs = document.querySelectorAll('input');
                    let emailInput = null;
                    let pwdInput = null;
                    
                    for (let inp of inputs) {
                        const type = inp.type || '';
                        const placeholder = inp.placeholder || '';
                        if (type === 'text' || placeholder.toLowerCase().includes('email') || placeholder.toLowerCase().includes('user')) {
                            emailInput = inp;
                        }
                        if (type === 'password' || placeholder.toLowerCase().includes('pass')) {
                            pwdInput = inp;
                        }
                    }
                    
                    if (!emailInput || !pwdInput) {
                        resolve({success: false, error: 'Could not find input fields'});
                        return;
                    }
                    
                    // Set values
                    emailInput.value = credentials.email;
                    emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                    emailInput.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    pwdInput.value = credentials.password;
                    pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
                    pwdInput.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    // Find and click submit button
                    const buttons = document.querySelectorAll('button');
                    let submitBtn = null;
                    for (let btn of buttons) {
                        const text = btn.innerText || btn.textContent || '';
                        if (text.toLowerCase().includes('login') || text.toLowerCase().includes('sign in') || btn.type === 'submit') {
                            submitBtn = btn;
                            break;
                        }
                    }
                    
                    if (!submitBtn) {
                        // Try submitting the form directly
                        const form = emailInput.closest('form');
                        if (form) {
                            form.dispatchEvent(new Event('submit', { bubbles: true }));
                            resolve({success: true, method: 'form_submit'});
                        } else {
                            resolve({success: false, error: 'No submit button or form found'});
                        }
                        return;
                    }
                    
                    submitBtn.click();
                    resolve({success: true, method: 'button_click'});
                });
            }''', {'email': 'tassochan@sri.sg', 'password': 'R028756g'})
            
            print(f"  Login attempt: {login_result}")
            
            # Wait for navigation after login
            await page.wait_for_timeout(8000)
            
            current_url = page.url
            print(f"[{datetime.now()}] Current URL: {current_url}")
            
            # Check if we're logged in (URL should change from login page)
            if 'login' in current_url:
                print(f"[{datetime.now()}] Still on login page, login may have failed")
                # Dump page text for debugging
                body_text = await page.evaluate('() => document.body.innerText')
                if 'incorrect' in body_text.lower() or 'error' in body_text.lower():
                    print(f"  Error text found on page")
                await browser.close()
                return None

            # Navigate to new launches
            print(f"[{datetime.now()}] Navigating to new launches...")
            await page.goto('https://app.singmap.com/#/new-launch-properties', wait_until='commit', timeout=20000)
            await page.wait_for_timeout(8000)
            
            # Extract project data from page
            projects = await page.evaluate('''() => {
                // Try multiple data sources
                const sources = [
                    () => { if (window.__NUXT__ && window.__NUXT__.state) {
                        for (let key of Object.keys(window.__NUXT__.state)) {
                            const val = window.__NUXT__.state[key];
                            if (val && val.lists && Array.isArray(val.lists)) return val.lists;
                            if (val && val.projects && Array.isArray(val.projects)) return val.projects;
                        }
                    }},
                    () => { for (let key of Object.keys(window)) {
                        try {
                            const val = window[key];
                            if (val && typeof val === 'object' && val.lists && Array.isArray(val.lists)) return val.lists;
                        } catch(e) {}
                    }},
                ];
                
                for (let fn of sources) {
                    const result = fn();
                    if (result && result.length > 0) return result;
                }
                return null;
            }''')

            if projects and isinstance(projects, list) and len(projects) > 0:
                print(f"[{datetime.now()}] Extracted {len(projects)} projects from page")
                await browser.close()
                return projects

            print(f"[{datetime.now()}] No project data found on page")
            await browser.close()
            return None

        except Exception as e:
            print(f"[{datetime.now()}] Error: {e}")
            await browser.close()
            return None

def clean_projects(raw_projects):
    cleaned = []
    for proj in raw_projects:
        cleaned.append({
            'project_name': proj.get('projectName') or proj.get('name'),
            'district': proj.get('district'),
            'location': proj.get('location'),
            'address': proj.get('streetAddress') or proj.get('address'),
            'property_type': proj.get('projectType') or proj.get('type'),
            'tenure': proj.get('tenure'),
            'min_price': proj.get('minPrice'),
            'max_price': proj.get('maxPrice'),
            'currency': proj.get('currencySymbol') or 'S$',
            'units': proj.get('unitsNum') or proj.get('units'),
            'completion_date': proj.get('completionDate') or proj.get('top'),
            'expected_top': proj.get('expTop'),
            'launch_date': proj.get('launchDate'),
            'sold_out': proj.get('soldOut') == 1,
            'latitude': proj.get('latitude'),
            'longitude': proj.get('longitude'),
            'cover_image': proj.get('mainImage') or proj.get('coverImage'),
        })
    return cleaned

def save_and_commit(projects):
    output = {
        'source': 'singmap.com',
        'total': len(projects),
        'scraped_at': datetime.utcnow().isoformat(),
        'projects': projects,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    CACHE_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[{datetime.now()}] Saved {len(projects)} projects")

    try:
        os.chdir("/home/hermes/initium-website")
        import subprocess
        subprocess.run(["git", "add", "ecoprop_projects.json"], check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"Auto-update projects from SingMap: {len(projects)} projects"],
                check=True, capture_output=True
            )
            subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
            print(f"[{datetime.now()}] Committed and pushed")
    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")

async def main():
    print(f"[{datetime.now()}] Starting SingMap scraper...")
    raw_projects = await fetch_from_singmap()
    if raw_projects:
        projects = clean_projects(raw_projects)
        save_and_commit(projects)
        print(f"[{datetime.now()}] SUCCESS: {len(projects)} projects")
    else:
        print(f"[{datetime.now()}] FAILED - keeping existing data")

if __name__ == '__main__':
    asyncio.run(main())
