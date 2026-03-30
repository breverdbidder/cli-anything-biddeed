#!/usr/bin/env python3
"""Enterprise-Grade Deployment Verifier — HARDCODED 10-POINT CHECK
This script is the GATE. Nothing is shipped without ALL 10 passing.
Committed as base64 to prevent accidental modification."""

import json, sys, time, os, subprocess
from datetime import datetime, timezone

def run_verification(url, selectors, test_input="1600 Orlando Ave Cocoa Beach FL"):
    from playwright.sync_api import sync_playwright
    
    results = {
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "screenshots": {},
        "enterprise_grade": False,
    }
    
    console_errors = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # === CHECK 1: HTTP 200 ===
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        start = time.time()
        resp = page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(5000)
        load_ms = int((time.time() - start) * 1000)
        
        results["checks"]["1_http_200"] = resp.status == 200 if resp else False
        results["load_ms"] = load_ms
        
        # === CHECK 2: Desktop screenshot ===
        page.screenshot(path="/tmp/verify-desktop.png", timeout=15000)
        results["checks"]["2_desktop_screenshot"] = os.path.exists("/tmp/verify-desktop.png")
        results["screenshots"]["desktop"] = "/tmp/verify-desktop.png"
        
        # === CHECK 3: Mobile responsive ===
        mobile = browser.new_page(viewport={"width": 375, "height": 812})
        mobile.goto(url, wait_until="networkidle", timeout=30000)
        mobile.wait_for_timeout(3000)
        mobile.screenshot(path="/tmp/verify-mobile.png", timeout=15000)
        scroll_w = mobile.evaluate("document.documentElement.scrollWidth")
        client_w = mobile.evaluate("document.documentElement.clientWidth")
        results["checks"]["3_mobile_responsive"] = scroll_w <= client_w
        results["screenshots"]["mobile"] = "/tmp/verify-mobile.png"
        mobile.close()
        
        # === CHECK 4: Thread renders (.aui-root) ===
        aui = page.query_selector(".aui-root, .aui-thread-root")
        results["checks"]["4_thread_renders"] = aui is not None
        
        # === CHECK 5: Textarea exists ===
        textarea = page.query_selector("textarea")
        results["checks"]["5_textarea_exists"] = textarea is not None
        
        # === CHECK 6: Grid/split-screen ===
        grid = page.query_selector("[class*=grid], [class*='w-[40']")
        results["checks"]["6_split_screen"] = grid is not None
        
        # === CHECK 7: Functional test ===
        if textarea:
            textarea.fill(test_input)
            page.keyboard.press("Enter")
            page.wait_for_timeout(20000)
            body_text = page.text_content("body") or ""
            keywords = ["parcel", "zone", "ru-1", "residential", "commercial", "setback", "height"]
            results["checks"]["7_functional_response"] = any(kw in body_text.lower() for kw in keywords)
            page.screenshot(path="/tmp/verify-functional.png", timeout=15000)
            results["screenshots"]["functional"] = "/tmp/verify-functional.png"
        else:
            results["checks"]["7_functional_response"] = False
        
        # === CHECK 8: Zero console errors ===
        results["checks"]["8_zero_console_errors"] = len(console_errors) == 0
        if console_errors:
            results["console_errors"] = console_errors[:10]
        
        browser.close()
    
    # === CHECK 9: Upload screenshots to Supabase ===
    supa_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    srk = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uploaded = []
    
    if srk:
        for name, path in results["screenshots"].items():
            if os.path.exists(path):
                obj_path = f"deployment-screenshots/chat-v2-{name}-{ts}.png"
                cmd = [
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "-X", "POST",
                    f"{supa_url}/storage/v1/object/{obj_path}",
                    "-H", f"Authorization: Bearer {srk}",
                    "-H", "Content-Type: image/png",
                    "--data-binary", f"@{path}"
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.stdout.strip() == "200":
                    public_url = f"{supa_url}/storage/v1/object/public/{obj_path}"
                    uploaded.append({"name": name, "url": public_url})
    
    results["checks"]["9_screenshots_uploaded"] = len(uploaded) >= 2
    results["uploaded_urls"] = uploaded
    
    # === CHECK 10: All checks pass ===
    passed = sum(1 for v in results["checks"].values() if v and v is not True or v is True)
    passed = sum(1 for v in results["checks"].values() if v)
    total = len(results["checks"])
    results["checks"]["10_all_pass"] = passed >= 9  # 9 real checks + this meta-check
    
    results["passed"] = passed
    results["total"] = total
    results["enterprise_grade"] = all(v for k, v in results["checks"].items() if k != "10_all_pass")
    
    return results


def post_to_issue(results, repo, issue_number, pat):
    """Post verification results as GitHub issue comment."""
    rows = []
    for check, passed in results["checks"].items():
        icon = "✅" if passed else "❌"
        rows.append(f"| {icon} | `{check}` |")
    
    table = "| Status | Check |\n|--------|-------|\n" + "\n".join(rows)
    
    urls = "\n".join([f"- [{u['name']}]({u['url']})" for u in results.get("uploaded_urls", [])])
    
    verdict = "🟢 **ENTERPRISE-GRADE — PAID-CUSTOMER READY**" if results["enterprise_grade"] else "🔴 **NOT ENTERPRISE-GRADE — NEEDS FIXES**"
    
    body = f"""## Playwright Verification — {results['url']}
**Timestamp:** {results['timestamp']}
**Load time:** {results.get('load_ms', '?')}ms
**Score:** {results['passed']}/{results['total']}

{table}

### Screenshots
{urls or 'None uploaded'}

### Verdict
{verdict}
"""
    
    if results.get("console_errors"):
        body += f"\n### Console Errors\n```\n" + "\n".join(results["console_errors"][:5]) + "\n```"
    
    import urllib.request
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        data=data,
        headers={"Authorization": f"token {pat}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req)
    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://zonewise.ai/chat-v2"
    selectors = sys.argv[2] if len(sys.argv) > 2 else ".aui-root,textarea,[class*=grid]"
    
    results = run_verification(url, selectors.split(","))
    
    print(json.dumps(results, indent=2, default=str))
    
    # Post to issue if env vars set
    issue = os.environ.get("GITHUB_ISSUE_NUMBER")
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPO", "breverdbidder/cli-anything-biddeed")
    if issue and pat:
        post_to_issue(results, repo, issue, pat)
        print(f"Results posted to issue #{issue}")
    
    sys.exit(0 if results["enterprise_grade"] else 1)
