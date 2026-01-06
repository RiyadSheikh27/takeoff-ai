"""
Diagnostic Script - Test API Keys and Environment
Run this BEFORE your Django app to verify everything works
"""

import os
import sys

print("="*70)
print("🔬 API ENVIRONMENT DIAGNOSTIC")
print("="*70)

# Test 1: Check Python packages
print("\n📦 CHECKING INSTALLED PACKAGES...")
try:
    import fitz
    print(f"   ✅ PyMuPDF: {fitz.__version__}")
except ImportError:
    print("   ❌ PyMuPDF: NOT INSTALLED")
    print("   💡 Run: pip install pymupdf")

try:
    import openai
    print(f"   ✅ OpenAI: {openai.__version__}")
except ImportError:
    print("   ❌ OpenAI: NOT INSTALLED")
    print("   💡 Run: pip install openai")

try:
    import google.generativeai as genai
    print(f"   ✅ Google Generative AI: Installed")
except ImportError:
    print("   ❌ Google Generative AI: NOT INSTALLED")
    print("   💡 Run: pip install google-generativeai")

try:
    import pandas as pd
    print(f"   ✅ Pandas: {pd.__version__}")
except ImportError:
    print("   ❌ Pandas: NOT INSTALLED")

try:
    import openpyxl
    print(f"   ✅ Openpyxl: {openpyxl.__version__}")
except ImportError:
    print("   ❌ Openpyxl: NOT INSTALLED")

try:
    from PIL import Image
    print(f"   ✅ Pillow: Installed")
except ImportError:
    print("   ❌ Pillow: NOT INSTALLED")

# Test 2: Check API Keys from settings
print("\n🔑 CHECKING API KEYS FROM DJANGO SETTINGS...")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
    import django
    django.setup()
    from django.conf import settings
    
    openai_key = getattr(settings, 'OPENAI_API_KEY', '')
    gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
    
    print(f"   OpenAI Key: {'Present' if openai_key else 'MISSING'} ({len(openai_key)} chars)")
    print(f"   Gemini Key: {'Present' if gemini_key else 'MISSING'} ({len(gemini_key)} chars)")
    
    if openai_key:
        print(f"   OpenAI Key Preview: {openai_key[:20]}...{openai_key[-10:]}")
    if gemini_key:
        print(f"   Gemini Key Preview: {gemini_key[:20]}...{gemini_key[-10:]}")
    
except Exception as e:
    print(f"   ⚠️ Django not configured: {e}")
    print("   Testing with hardcoded keys instead...")
    
    # Hardcoded keys for testing (replace with your actual keys)
    openai_key = "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"
    gemini_key = "AIzaSyDh-4IE-nGaYH_I_UMm-S8cWEPDuC4nbHI"
    
    print(f"   OpenAI Key: {len(openai_key)} chars")
    print(f"   Gemini Key: {len(gemini_key)} chars")

# Test 3: Test OpenAI API
print("\n🤖 TESTING OPENAI API...")
if openai_key:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        # Simple test call (text only, no image)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for testing
            messages=[{"role": "user", "content": "Say 'API works!'"}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        print(f"   ✅ OpenAI API WORKS! Response: {result}")
        
    except Exception as e:
        print(f"   ❌ OpenAI API FAILED: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
else:
    print("   ⏭️ Skipped (no key)")

# Test 4: Test Gemini API
print("\n🔮 TESTING GEMINI API...")
if gemini_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        # Simple test call (text only)
        response = model.generate_content("Say 'API works!'")
        result = response.text
        print(f"   ✅ Gemini API WORKS! Response: {result}")
        
    except Exception as e:
        print(f"   ❌ Gemini API FAILED: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
else:
    print("   ⏭️ Skipped (no key)")

# Test 5: Test PDF Processing
print("\n📄 TESTING PDF PROCESSING...")
try:
    import fitz
    from PIL import Image
    from io import BytesIO
    import base64
    
    # Create a dummy PDF
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 100), "W30X90 Test Beam", fontsize=20)
    
    test_pdf = "/tmp/test_drawing.pdf"
    doc.save(test_pdf)
    doc.close()
    
    print(f"   ✅ Created test PDF: {test_pdf}")
    
    # Test rendering
    doc = fitz.open(test_pdf)
    page = doc[0]
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    
    print(f"   ✅ Rendered to image: {len(img_bytes):,} bytes")
    
    # Test PIL conversion
    img = Image.open(BytesIO(img_bytes))
    print(f"   ✅ PIL conversion: {img.size[0]}x{img.size[1]}")
    
    # Test base64 encoding
    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
    print(f"   ✅ Base64 encoding: {len(img_b64):,} chars")
    
    doc.close()
    
except Exception as e:
    print(f"   ❌ PDF processing failed: {str(e)}")

print("\n" + "="*70)
print("✅ DIAGNOSTIC COMPLETE")
print("="*70)
print("\n💡 NEXT STEPS:")
print("   1. Fix any ❌ errors above")
print("   2. Verify API keys are correct and not expired")
print("   3. Make sure all packages are installed")
print("   4. Test with your actual PDF")
print("="*70)