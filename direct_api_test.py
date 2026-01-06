#!/usr/bin/env python3
"""
Direct API Test - Use your actual PDF and keys
Run this OUTSIDE Django to isolate the issue
"""

import os
import sys

# Add your Django project to path
sys.path.insert(0, '/home/riyadsheikh/Riyad/app')  # Adjust this path

# ============================================================================
# STEP 1: Load settings
# ============================================================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')  # Change 'your_project'

try:
    import django
    django.setup()
    from django.conf import settings
    
    OPENAI_KEY = settings.OPENAI_API_KEY
    GEMINI_KEY = settings.GEMINI_API_KEY
    print(f"✅ Loaded from Django settings")
except:
    # Fallback: Hardcode keys for testing
    print("⚠️ Django settings not loaded, using hardcoded keys")
    OPENAI_KEY = "YOUR_NEW_OPENAI_KEY_HERE"  # ← PASTE YOUR NEW KEY HERE
    GEMINI_KEY = "AIzaSyDh-4IE-nGaYH_I_UMm-S8cWEPDuC4nbHI"

print(f"\n{'='*70}")
print("🔬 DIRECT API TEST WITH REAL PDF")
print(f"{'='*70}\n")

# ============================================================================
# STEP 2: Check keys
# ============================================================================
print("🔑 CHECKING API KEYS...")
print(f"   OpenAI: {len(OPENAI_KEY)} chars")
print(f"   First 20: {OPENAI_KEY[:20]}")
print(f"   Last 10: {OPENAI_KEY[-10:]}")
print(f"   Gemini: {len(GEMINI_KEY)} chars")
print(f"   First 20: {GEMINI_KEY[:20]}")

# Validate OpenAI key format
if not OPENAI_KEY.startswith('sk-'):
    print("\n❌ CRITICAL: OpenAI key doesn't start with 'sk-'")
    print("   Your key is INVALID!")
    exit(1)

if len(OPENAI_KEY) > 100:
    print(f"\n⚠️ WARNING: OpenAI key is {len(OPENAI_KEY)} chars (should be ~51)")
    print("   Key might be corrupted or contain extra characters")
    print("   Attempting to clean it...")
    OPENAI_KEY = OPENAI_KEY.strip()
    print(f"   After strip: {len(OPENAI_KEY)} chars")

# ============================================================================
# STEP 3: Test with small image first
# ============================================================================
print("\n🧪 TEST 1: Small test image (should be fast)...")

import fitz
from PIL import Image
from io import BytesIO
import base64

# Create tiny test PDF
doc = fitz.open()
page = doc.new_page(width=612, height=792)
page.insert_text((100, 100), "W30X90", fontsize=50)
page.insert_text((100, 200), "W27X84", fontsize=50)
test_pdf = "/tmp/tiny_test.pdf"
doc.save(test_pdf)
doc.close()

# Render at LOW DPI first (faster)
doc = fitz.open(test_pdf)
pix = doc[0].get_pixmap(dpi=72)  # Low DPI for speed
img_bytes = pix.tobytes("png")
img_b64 = base64.b64encode(img_bytes).decode('utf-8')
doc.close()

print(f"   Created tiny test: {len(img_b64):,} chars base64")

# Test OpenAI
print("\n🤖 Testing OpenAI with tiny image...")
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    print("   ✅ Client created")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cheaper model for testing
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Count steel members. Return JSON: {\"W30X90\": 1}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        }],
        max_tokens=500
    )
    
    result = response.choices[0].message.content
    print(f"   ✅ OpenAI WORKS!")
    print(f"   Response: {result}")
    
except Exception as e:
    print(f"   ❌ OpenAI FAILED: {str(e)}")
    print(f"\n   Full error type: {type(e).__name__}")
    
    if "401" in str(e) or "Incorrect API key" in str(e):
        print("\n   💡 FIX: Your API key is INVALID")
        print("   1. Go to: https://platform.openai.com/api-keys")
        print("   2. Create NEW key")
        print("   3. Copy ENTIRE key (should be ~51 chars)")
        print("   4. Update settings.py")
    elif "429" in str(e):
        print("\n   💡 FIX: Rate limit or no billing")
        print("   Check: https://platform.openai.com/account/billing")

# Test Gemini
print("\n🔮 Testing Gemini with tiny image...")
try:
    # Try new package first
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        print("   ✅ Using NEW google-genai package")
        use_new = True
    except ImportError:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_KEY)
        model = genai_old.GenerativeModel("gemini-2.0-flash-exp")
        print("   ⚠️ Using OLD deprecated package")
        use_new = False
    
    img = Image.open(BytesIO(img_bytes))
    
    if use_new:
        from google.genai import types
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                'Count steel members. Return JSON: {"W30X90": 1}',
                types.Part.from_image(img)
            ]
        )
        result = response.text
    else:
        response = model.generate_content([
            'Count steel members. Return JSON: {"W30X90": 1}',
            img
        ])
        result = response.text
    
    print(f"   ✅ Gemini WORKS!")
    print(f"   Response: {result}")
    
except Exception as e:
    print(f"   ❌ Gemini FAILED: {str(e)}")

# ============================================================================
# STEP 4: Test with YOUR actual PDF
# ============================================================================
print("\n" + "="*70)
PDF_PATH = input("\n📄 Enter path to your PDF (or press Enter to skip): ").strip()

if PDF_PATH and os.path.exists(PDF_PATH):
    print(f"\n🧪 TEST 2: Your actual PDF...")
    
    doc = fitz.open(PDF_PATH)
    print(f"   Pages: {len(doc)}")
    
    # Test FIRST page only at LOWER DPI
    page = doc[0]
    print(f"   Rendering page 1 at 150 DPI (smaller than your 200)...")
    
    pix = page.get_pixmap(dpi=150)  # Reduced from 200
    img_bytes = pix.tobytes("png")
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    
    print(f"   Rendered: {len(img_b64):,} chars base64")
    print(f"   Size: {len(img_bytes):,} bytes")
    
    img = Image.open(BytesIO(img_bytes))
    print(f"   Dimensions: {img.size[0]}x{img.size[1]}")
    
    # Test OpenAI with real PDF
    print("\n   🤖 Testing OpenAI with your PDF...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        
        import time
        start = time.time()
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Count ALL steel members. Return ONLY JSON."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=2000,
            temperature=0.1,
            timeout=60.0  # 60 second timeout
        )
        
        elapsed = time.time() - start
        result = response.choices[0].message.content
        
        print(f"   ✅ OpenAI responded in {elapsed:.1f}s")
        print(f"   Response length: {len(result)} chars")
        print(f"   Preview: {result[:300]}...")
        
        # Try to parse JSON
        import json, re
        json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            print(f"   ✅ Found {len(parsed)} member types")
            print(f"   Total count: {sum(parsed.values())}")
        else:
            print("   ⚠️ No JSON found in response")
        
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        if "timeout" in str(e).lower():
            print("   💡 Image too large - API timed out")
            print("   Try reducing DPI to 100 or 120")
    
    doc.close()

else:
    print("\n⏭️ Skipping real PDF test")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("📊 DIAGNOSTIC SUMMARY")
print("="*70)

print("\n✅ IF TINY TEST WORKED BUT REAL PDF FAILED:")
print("   → Your keys are VALID")
print("   → Problem is image SIZE (2.8MB is too large)")
print("   → Solution: Reduce DPI from 200 to 120-150")

print("\n❌ IF TINY TEST FAILED:")
print("   → Your OpenAI key is INVALID")
print("   → Get new key from: https://platform.openai.com/api-keys")
print("   → Make sure it's ~51 characters, not 164")

print("\n💡 TO FIX YOUR DJANGO APP:")
print("   1. Get correct OpenAI key (51 chars)")
print("   2. Update settings.py")
print("   3. In core.py, change line:")
print("      pix = page.get_pixmap(dpi=200)")
print("      to:")
print("      pix = page.get_pixmap(dpi=120)")
print("   4. Restart Django server")

print("\n" + "="*70)