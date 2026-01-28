import argparse
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import sys
import os

def scrape_ads_count(page, url):
    """
    Scrapes the number of ads from the Google Ads Transparency Center URL using an existing page.
    Returns the count string or 'no ads'/'Error'.
    """
    try:
        # Go to URL with a timeout
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Check for "0 ads" or count
        # Based on investigation: .ads-count-searchable
        try:
            locator = page.locator(".ads-count-searchable")
            try:
                locator.wait_for(state="visible", timeout=30000)
                text = locator.inner_text().strip()
                if text == "0 ads":
                    return "no ads"
                else:
                    return text
            except:
                # If timeout waiting for selector, check for "No ads found" text
                if page.get_by_text("No ads found").count() > 0:
                    return "no ads"
                else:
                    # Specific to user request: "if nothing then return no ads"
                    # We can be aggressive here. If we don't find the count, assume no ads or verify further?
                    # Let's check if the page loaded at least.
                    if "Google Ads" in page.title():
                         return "no ads"
                    return "Error: Element not found"
        except Exception as e:
            return f"Error: {str(e)}"
            
    except Exception as e:
        return f"Error loading page: {str(e)}"

def process_csv(input_path, output_path, progress_callback=None):
    """
    Reads input CSV, scrapes data, and writes to output CSV.
    progress_callback(current, total, message) is called if provided.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file '{input_path}' not found.")

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        raise Exception(f"Error reading CSV: {e}")

    # Detect URL column
    url_col = None
    for col in df.columns:
        if "url" in col.lower() or "link" in col.lower():
            url_col = col
            break
    
    if not url_col:
        # Fallback: check if the first column looks like a URL
        first_val = str(df.iloc[0, 0])
        if first_val.startswith("http"):
            url_col = df.columns[0]
        else:
            raise Exception("Could not detect a URL column. Please name it 'url' or similar.")

    if progress_callback:
        progress_callback(0, len(df), f"Found {len(df)} rows. Using column '{url_col}'...")

    # Create new column
    if "number of ads" not in df.columns:
        df["number of ads"] = ""

    extracted_counts = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        for index, row in df.iterrows():
            url = row[url_col]
            if progress_callback:
                progress_callback(index + 1, len(df), f"Processing {index + 1}/{len(df)}: {str(url)[:50]}...")

            if pd.isna(url) or not str(url).startswith("http"):
                extracted_counts.append("Invalid URL")
                continue
                
            # Retry loop mechanism
            max_retries = 3
            result = "Error: Element not found"
            
            for attempt in range(max_retries):
                page = context.new_page()
                try:
                    # Increased page load timeout to 90s
                    page.goto(url, wait_until="domcontentloaded", timeout=90000)
                    
                    # Logic inside scrape_ads_count needs to be resilient
                    # We pass the page object as before
                    
                    try:
                        locator = page.locator(".ads-count-searchable")
                        # Increased element wait timeout to 60s
                        locator.wait_for(state="visible", timeout=60000)
                        
                        text = locator.inner_text().strip()
                        if text == "0 ads":
                            result = "no ads"
                        else:
                            result = text
                        
                        # If successful, break retry loop
                        break
                        
                    except:
                        # Fallback checks
                        if page.get_by_text("No ads found").count() > 0:
                            result = "no ads"
                            break
                        
                        if "Google Ads" in page.title():
                             result = "Error: Element not found (Timeout)"
                        else:
                             result = "Error: Page load failed"
                             
                except Exception as e:
                    result = f"Error: {str(e)}"
                finally:
                    page.close()
                
                # If we are here and didn't result in success, wait a bit before retry
                if attempt < max_retries - 1:
                    time.sleep(2)
            
            extracted_counts.append(result)
            
            # Polite delay
            time.sleep(1)
        
        browser.close()
        
    df["number of ads"] = extracted_counts
    
    try:
        df.to_csv(output_path, index=False)
        if progress_callback:
            progress_callback(len(df), len(df), f"Done! Saved to {output_path}")
    except Exception as e:
        raise Exception(f"Error writing output CSV: {e}")

def main():
    parser = argparse.ArgumentParser(description="Scrape Google Ads Transparency Center ad counts.")
    parser.add_argument("input_csv", help="Path to input CSV file")
    parser.add_argument("output_csv", help="Path to output CSV file")
    args = parser.parse_args()

    def console_progress(current, total, message):
        print(message)

    try:
        process_csv(args.input_csv, args.output_csv, console_progress)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
