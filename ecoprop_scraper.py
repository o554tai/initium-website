import asyncio
import json
from playwright.async_api import async_playwright

async def scrape_ecoprop():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.new_page()
        await page.goto('https://www.ecoprop.com/new-launch-properties', wait_until='networkidle')
        await page.wait_for_timeout(2000)

        all_projects = []

        # Use the site's own JS context to call the API with large pageSize
        for page_no in [1, 2]:
            result = await page.evaluate(f'''async () => {{
                function generateSignature(params) {{
                    const base = {{
                        appSource: "web",
                        lang: "en",
                        timestamp: new Date().getTime().toString(),
                    }};
                    const merged = {{...base, ...params}};
                    const sortedKeys = Object.keys(merged).sort();
                    let sigStr = "";
                    for (let k of sortedKeys) {{
                        if (k !== "token" && merged[k] != null) {{
                            sigStr += String(merged[k]);
                        }}
                    }}
                    sigStr += "c1d65f3667324592a071ebec5038f38c";
                    return window.$nuxt.$md5(sigStr);
                }}

                const timestamp = new Date().getTime().toString();
                const params = {{
                    lang: "en",
                    timestamp: timestamp,
                    country: "Singapore",
                    type: "",
                    soldOut: "",
                    minPrice: "",
                    maxPrice: "",
                    bedrooms: "",
                    projectType: "",
                    tenure: "",
                    completionStatus: "",
                    projectArea: "",
                    category: "",
                    minArea: "",
                    maxArea: "",
                    projectName: "",
                    location: "",
                    pageNo: "{page_no}",
                    pageSize: "500",
                    pointJson: "",
                    year: "",
                    orderRule: "projectName",
                    distance: "",
                    total: "web",
                    vrCall: "",
                }};

                const sig = generateSignature(params);
                const formData = new URLSearchParams();
                for (let k in params) formData.append(k, params[k]);
                formData.append("signature", sig);
                formData.append("appSource", "web");

                const resp = await fetch("https://api.singmap.com/c-api/project/queryProjectList", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json, text/plain, */*",
                        "Referer": "https://www.ecoprop.com/",
                    }},
                    body: formData.toString(),
                }});
                const data = await resp.json();
                if (data.code === "0" && data.datas && data.datas.lists) {{
                    return {{
                        count: data.datas.count,
                        projects: data.datas.lists,
                    }};
                }}
                return {{error: data.msg || "unknown"}};
            }}''')

            if 'error' in result:
                print(f"Page {page_no} error: {result['error']}")
                break
            projects = result.get('projects', [])
            total_count = result.get('count', 0)
            all_projects.extend(projects)
            print(f"Page {page_no}: {len(projects)} projects (total: {len(all_projects)}/{total_count})")
            if len(projects) == 0 or len(all_projects) >= total_count:
                break

        print(f"\nTotal projects fetched: {len(all_projects)}")

        # Clean and structure
        cleaned = []
        for proj in all_projects:
            cleaned.append({
                'project_name': proj.get('projectName'),
                'district': proj.get('district'),
                'location': proj.get('location'),
                'address': proj.get('streetAddress'),
                'property_type': proj.get('projectType'),
                'tenure': proj.get('tenure'),
                'min_price': proj.get('minPrice'),
                'max_price': proj.get('maxPrice'),
                'currency': proj.get('currencySymbol'),
                'units': proj.get('unitsNum'),
                'completion_date': proj.get('completionDate'),
                'expected_top': proj.get('expTop'),
                'launch_date': proj.get('launchDate'),
                'sold_out': proj.get('soldOut') == 1,
                'latitude': proj.get('latitude'),
                'longitude': proj.get('longitude'),
                'cover_image': f"https://img.singmap.com{proj.get('mainImage')}" if proj.get('mainImage') else None,
            })

        output = {
            'source': 'ecoprop.com',
            'total': len(cleaned),
            'projects': cleaned,
        }

        with open('/home/hermes/ecoprop_projects.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print("Saved to /home/hermes/ecoprop_projects.json")
        if cleaned:
            print("\nSample:")
            for proj in cleaned[:5]:
                print(f"  - {proj['project_name']} | {proj['district']} | {proj['location']} | {proj['currency']}{proj['min_price']} - {proj['currency']}{proj['max_price']} | {proj['property_type']} | TOP: {proj['completion_date']} | {proj['tenure']}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(scrape_ecoprop())
