import os
import time
import requests
import shutil
from playwright.sync_api import sync_playwright

def download_image(url, folder, index):
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            # Determine extension, default to .png if not clear, or force .png as requested
            # The user asked to rename them to 1.png, 2.png etc. 
            # We will save as .png regardless of source logic for simplicity of naming, 
            # though converting fully might require Pillow. 
            # For now, we'll just save the bytes with .png extension as requested.
            file_path = os.path.join(folder, f"{index}.png")
            with open(file_path, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
            print(f"Downloaded: {file_path}")
            return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return False

def main():
    query = input("query: ").strip()
    if not query:
        print("Query cannot be empty.")
        return

    amount_str = input("amount: ").strip()
    if not amount_str.isdigit():
        print("Amount must be a number.")
        return
    amount = int(amount_str)

    dump_num_str = input("dump_num: ").strip()
    if not dump_num_str.isdigit():
        print("dump_num must be a number.")
        return
    dump_num = int(dump_num_str)

    # Prepare folder
    folder_name = query.replace(" ", "-")
    assets_dir = os.path.join(os.getcwd(), "assets", folder_name, f"dump_{dump_num}")
    
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        print(f"Created directory: {assets_dir}")
    else:
        print(f"Using existing directory: {assets_dir}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False to see what's happening, often better for scrapers
        page = browser.new_page()
        
        search_url = f"https://www.pinterest.com/search/pins/?q={query}"
        print(f"Navigating to {search_url}...")
        page.goto(search_url)

        # Collect image URLs
        image_urls = set()
        print("Scraping images...")
        
        last_height = page.evaluate("document.body.scrollHeight")
        
        while len(image_urls) < amount:
            # Find all images
            # Pinterest often uses 'img' tags with verify meaningful structure.
            # We look for img tags that are likely pins (usually larger).
            # Selector might need adjustment based on Pinterest's current DOM.
            # a common selector for pin images is img[src*="pinimg.com/236x/"] or similar, 
            # but we want high res. usually the source set includes variants.
            # We will grab 'src' or 'srcset' and try to find the biggest.
            
            # Simplified approach: grabbing all images on screen and filtering
            elements = page.query_selector_all("img")
            
            for img in elements:
                if len(image_urls) >= amount:
                    break
                
                try:
                    src = img.get_attribute("src")
                    if src and "pinimg.com" in src:
                        # Check size
                        box = img.bounding_box()
                        if box and box['width'] > 75 and box['height'] > 75:
                            # Try to upgrade quality if possible. 
                            # Pinimg typically has /236x/ or /474x/ etc. 
                            # Replacing with /originals/ often works but not always.
                            # For safety, let's keep the one we found or try a safer high-res replacement.
                            high_res_src = src.replace("/236x/", "/originals/").replace("/474x/", "/originals/")
                            # Note: /originals/ might be different format (jpg/png).
                            
                            image_urls.add(src) # Use src for reliability if high_res logic is complex without checking existence
                except:
                    continue

            # Scroll down
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2) # Wait for load
            
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                print("Reached end of page or no more results loading.")
                break
            last_height = new_height
            print(f"Found {len(image_urls)} candidates so far...")

        browser.close()

        print(f"Starting download of {min(len(image_urls), amount)} images...")
        count = 0
        for url in image_urls:
            if count >= amount:
                break
                
            # Try to get high quality URL just before downloading
            # Common patterns: 236x, 474x, 564x, 736x
            # We want to try to get the largest possible. 
            # Let's try to swap to originals if valid, else fallback? 
            # Since checking validity adds time, we might just download the one we found 
            # ensuring it's not a tiny avatar (filtered by bbox/size check earlier).
            # To get better quality than thumbnail, let's try replacing /236x/ with /736x/ which is standard "large" pin.
            
            target_url = url
            if "/236x/" in url:
                target_url = url.replace("/236x/", "/736x/")
            
            # Simple 1-up counting
            if download_image(target_url, assets_dir, count + 1):
                count += 1
            else:
                # If 736x failed, try original url
                if target_url != url:
                    if download_image(url, assets_dir, count + 1):
                        count += 1

    print("Done!")

if __name__ == "__main__":
    main()
