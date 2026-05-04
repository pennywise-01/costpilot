from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    
    errors = []
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
    page.on("pageerror", lambda err: errors.append(f"[PAGE ERROR] {err}"))
    
    # Navigate to login
    page.goto("http://127.0.0.1:5173/login", timeout=15000)
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    
    print(f"URL: {page.url}")
    
    # Try to login
    email_input = page.locator('input[type="email"], input[placeholder*="email" i], input[id*="email" i]').first
    password_input = page.locator('input[type="password"]').first
    
    if email_input.is_visible(timeout=3000) and password_input.is_visible(timeout=3000):
        email_input.fill("test@test.com")
        password_input.fill("H4fz4n12@#")
        
        submit_btn = page.locator('button[type="submit"], button:has-text("Log in"), button:has-text("Sign in"), button:has-text("Login")').first
        if submit_btn.is_visible(timeout=3000):
            submit_btn.click()
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle", timeout=15000)
            
            print(f"After login URL: {page.url}")
            
            # Navigate to dashboard if not already there
            if "login" in page.url.lower():
                page.screenshot(path="/tmp/dashboard_login_failed.png", full_page=True)
                print("Login failed - still on login page")
            else:
                page.wait_for_timeout(3000)
                page.screenshot(path="/tmp/dashboard_page.png", full_page=True)
                print("Dashboard screenshot saved to /tmp/dashboard_page.png")
                
                # Check grid items
                grid_items = page.locator('.react-grid-item').all()
                print(f"Grid items: {len(grid_items)}")
                
                cards = page.locator('.ant-card').all()
                print(f"Ant cards: {len(cards)}")
                
                # Get computed styles of grid items
                for i, item in enumerate(grid_items[:3]):
                    box = item.bounding_box()
                    if box:
                        print(f"  Grid item {i}: x={box['x']:.0f}, y={box['y']:.0f}, w={box['width']:.0f}, h={box['height']:.0f}")
        else:
            print("No submit button found")
            page.screenshot(path="/tmp/dashboard_login_form.png", full_page=True)
    else:
        print("No login inputs found")
        page.screenshot(path="/tmp/dashboard_no_inputs.png", full_page=True)
    
    if errors:
        print("\n=== Console Errors/Warnings ===")
        for e in errors[:30]:
            print(e)
    else:
        print("\nNo console errors")
    
    browser.close()
