"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     MATERIAL TAKEOFF AI - CORE ENGINE                        ║
║                                                                              ║
║  Purpose: Extract structural steel members from PDF construction drawings    ║
║  Methods: OCR Text Extraction + Multi-AI Vision Analysis + AI Length Calc   ║
║  Output:  Excel Takeoff Report + Color-Coded Highlighted PDF                ║
║                                                                              ║
║  Author:  AI-Powered Construction Estimator                                 ║
║  Version: 3.0 - Enhanced with AI-Powered Length Determination               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import base64
import math
from io import BytesIO
from collections import Counter, defaultdict
from datetime import datetime
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: STEEL DATABASE & CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

"""
Standard steel member weights (lbs/ft) from AISC Steel Construction Manual.
This database covers common W-beams, HSS tubes, channels, and angles.
"""
STEEL_WEIGHTS = {
    # W-Beams (Wide Flange)
    "W30X90": 90, "W27X84": 84, "W24X55": 55, "W21X44": 44,
    "W18X35": 35, "W16X26": 26, "W14X22": 22, "W12X19": 19,
    "W10X15": 15, "W8X10": 10, "W6X9": 9,
    
    # HSS (Hollow Structural Sections)
    "HSS8X8X1/2": 40.23, "HSS6X6X3/8": 27.48, "HSS4X4X1/4": 12.21,
    "HSS10X6X3/8": 35.13, "HSS12X8X1/2": 58.10,
    
    # Channels (C and MC shapes)
    "C12X30": 30, "C10X25": 25, "C9X20": 20, "C8X18.75": 18.75,
    "MC18X58": 58, "MC13X50": 50, "MC12X45": 45,
    
    # Angles (L shapes)
    "L6X6X1/2": 19.6, "L5X5X3/8": 12.8, "L4X4X1/4": 6.6,
    "L8X8X1": 51.0, "L3X3X1/4": 4.9,
}

"""
Regular expressions for identifying different structural steel types.
These patterns match standard AISC designation formats.
"""
W_BEAM_PATTERN = re.compile(r"W\d+[xX]\d+", re.IGNORECASE)
HSS_PATTERN = re.compile(r"HSS\d+[xX]\d+[xX][\d/]+", re.IGNORECASE)
CHANNEL_PATTERN = re.compile(r"(?:MC|C)\d+[xX][\d.]+", re.IGNORECASE)
ANGLE_PATTERN = re.compile(r"L\d+[xX]\d+[xX][\d/]+", re.IGNORECASE)
JOIST_PATTERN = re.compile(r"\d{2}[KLH]+\d+", re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def normalize_member_designation(member_text):
    """
    Normalize steel member designation to standard format.
    
    Converts various input formats to consistent AISC standard:
    - Converts to uppercase
    - Standardizes 'x' to 'X'
    - Removes whitespace
    
    Args:
        member_text (str): Raw member designation (e.g., "w24x55", "W 24 X 55")
    
    Returns:
        str: Normalized designation (e.g., "W24X55")
    
    Example:
        >>> normalize_member_designation("w 24 x 55")
        'W24X55'
    """
    normalized = member_text.upper()
    normalized = re.sub(r"(?<=[0-9])x(?=[0-9])", "X", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def categorize_member(member_designation):
    """
    Categorize structural steel member by type.
    
    Identifies the structural category based on designation format.
    Used for color-coding in PDF markup and organizing takeoff results.
    
    Args:
        member_designation (str): Steel member designation
    
    Returns:
        str: Category name ('Beam', 'HSS', 'Channel', 'Angle', 'Joist', 'Other')
    
    Example:
        >>> categorize_member("W24X55")
        'Beam'
        >>> categorize_member("HSS8X8X1/2")
        'HSS'
    """
    member_upper = member_designation.upper()
    
    if member_upper.startswith("W") and "X" in member_upper:
        return "Beam"
    elif member_upper.startswith("HSS"):
        return "HSS"
    elif member_upper.startswith(("C", "MC")) and "X" in member_upper:
        return "Channel"
    elif member_upper.startswith("L") and member_upper.count("X") >= 2:
        return "Angle"
    elif re.match(r"\d{2}[KLH]", member_upper):
        return "Joist"
    else:
        return "Other"


def lookup_member_weight(member_designation):
    """
    Retrieve unit weight (lbs/ft) for steel member.
    
    Searches database first, then attempts to parse from W-beam designation.
    Falls back to conservative estimate if not found.
    
    Args:
        member_designation (str): Normalized steel designation
    
    Returns:
        float: Weight in pounds per linear foot
    
    Example:
        >>> lookup_member_weight("W24X55")
        55.0
        >>> lookup_member_weight("W30X90")
        90.0
    """
    # Direct database lookup
    if member_designation in STEEL_WEIGHTS:
        return STEEL_WEIGHTS[member_designation]
    
    # Parse W-beam weight from designation (W24X55 → 55 lbs/ft)
    if member_designation.startswith("W"):
        weight_match = re.search(r"X(\d+)", member_designation)
        if weight_match:
            return float(weight_match.group(1))
    
    # Conservative fallback estimate
    return 25.0


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: OCR TEXT EXTRACTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def extract_ocr(pdf_path):
    """
    Extract structural steel members from PDF using OCR text analysis.
    
    This is the PRIMARY extraction method. Uses PyMuPDF to:
    1. Extract all text from each PDF page
    2. Identify steel members using regex patterns
    3. Record positions for visual markup
    4. Track dimensions for quantity verification
    
    Process Flow:
        PDF → Text Extraction → Pattern Matching → Position Mapping → Results
    
    Args:
        pdf_path (str): Full path to PDF file
    
    Returns:
        dict: {
            'counts': {category: Counter({member: count})},
            'positions': {member: [{'page': int, 'bbox': tuple}]},
            'text_items': [{text, x, y, bbox, page}]
        }
    
    Console Output:
        Prints detailed page-by-page statistics with member counts
    """
    print("\n" + "="*80)
    print("📄 STEP 1: OCR TEXT EXTRACTION")
    print("="*80)
    print(f"File: {os.path.basename(pdf_path)}\n")
    
    # Open PDF document
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"📖 Total pages: {total_pages}")
    
    # Initialize storage structures
    counts = {
        "beams": Counter(),
        "hss": Counter(),
        "channels": Counter(),
        "angles": Counter(),
        "joists": Counter(),
    }
    positions = defaultdict(list)  # member → list of locations
    all_text_items = []  # For dimension extraction
    
    # Process each page
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        
        # Track page statistics
        page_counts = {
            "beams": 0, "hss": 0, "channels": 0,
            "angles": 0, "joists": 0
        }
        
        # Find W-beams (e.g., W24X55)
        for match in W_BEAM_PATTERN.finditer(text):
            member = normalize_member_designation(match.group())
            counts["beams"][member] += 1
            page_counts["beams"] += 1
        
        # Find HSS tubes (e.g., HSS8X8X1/2)
        for match in HSS_PATTERN.finditer(text):
            member = normalize_member_designation(match.group())
            counts["hss"][member] += 1
            page_counts["hss"] += 1
        
        # Find channels (e.g., C12X30)
        for match in CHANNEL_PATTERN.finditer(text):
            member = normalize_member_designation(match.group())
            counts["channels"][member] += 1
            page_counts["channels"] += 1
        
        # Find angles (e.g., L6X6X1/2)
        for match in ANGLE_PATTERN.finditer(text):
            member = normalize_member_designation(match.group())
            counts["angles"][member] += 1
            page_counts["angles"] += 1
        
        # Find joists (e.g., 24K9)
        for match in JOIST_PATTERN.finditer(text):
            member = normalize_member_designation(match.group())
            counts["joists"][member] += 1
            page_counts["joists"] += 1
        
        # Print page summary
        print(f"  Page {page_num+1}: Beams={page_counts['beams']}, "
              f"HSS={page_counts['hss']}, Channels={page_counts['channels']}, "
              f"Angles={page_counts['angles']}, Joists={page_counts['joists']}")
        
        # Extract positioned text blocks for markup and dimensions
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        
                        # Store all text items for dimension detection
                        if span_text and len(span_text) > 1:
                            bbox = span["bbox"]
                            all_text_items.append({
                                'text': span_text,
                                'x': (bbox[0] + bbox[2]) / 2,
                                'y': (bbox[1] + bbox[3]) / 2,
                                'bbox': bbox,
                                'page': page_num,
                            })
                        
                        # Record positions for each detected member
                        for pattern in [W_BEAM_PATTERN, HSS_PATTERN, CHANNEL_PATTERN,
                                       ANGLE_PATTERN, JOIST_PATTERN]:
                            for match in pattern.finditer(span["text"]):
                                member_norm = normalize_member_designation(match.group())
                                positions[member_norm].append({
                                    "page": page_num,
                                    "bbox": span["bbox"]
                                })
    
    doc.close()
    
    # Print final summary
    total_members = sum(sum(c.values()) for c in counts.values())
    print(f"\n✅ OCR Complete: {total_members} members found")
    print(f"   Beams: {sum(counts['beams'].values())}")
    print(f"   HSS: {sum(counts['hss'].values())}")
    print(f"   Channels: {sum(counts['channels'].values())}")
    print(f"   Angles: {sum(counts['angles'].values())}")
    print(f"   Joists: {sum(counts['joists'].values())}")
    print("="*80)
    
    return {
        "counts": counts,
        "positions": dict(positions),
        "text_items": all_text_items
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: AI VISION ANALYSIS - OPENAI GPT-4O
# ══════════════════════════════════════════════════════════════════════════════

def analyze_openai(pdf_path, api_key):
    """
    Analyze PDF with OpenAI GPT-4O Vision model.
    
    Sends high-resolution page images to GPT-4O for structural member detection.
    This provides AI-powered verification of OCR results and catches members
    that OCR might miss (faded text, handwritten notes, etc.).
    """
    print("\n" + "="*80)
    print("🤖 STEP 2: OPENAI GPT-4O VISION ANALYSIS")
    print("="*80)
    
    # Skip if no API key provided
    if not api_key:
        print("⚠️  No API key - SKIPPED\n" + "="*80)
        return Counter()
    
    # Show masked API key for verification
    print(f"🔑 API Key: {'*' * (len(api_key)-8)}{api_key[-8:]}\n")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        doc = fitz.open(pdf_path)
        all_counts = Counter()
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"📸 Page {page_num+1}: ", end="")
            
            try:
                # Convert page to high-res image
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                
                print(f"Sending {len(img_bytes):,} bytes... ", end="")
                
                # Call OpenAI Vision API
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    'Count ALL structural steel members visible in this drawing. '
                                    'Return ONLY valid JSON with member designations as keys and counts as values. '
                                    'Example format: {"W30X90": 12, "HSS8X8X1/2": 6, "C12X30": 4}'
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}",
                                    "detail": "high"
                                }
                            },
                        ],
                    }],
                    max_tokens=2000,
                    temperature=0.1,
                )
                
                # Parse JSON response
                content = response.choices[0].message.content
                json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                
                if json_match:
                    parsed_data = json.loads(json_match.group())
                    page_total = sum(parsed_data.values())
                    print(f"✅ Found {len(parsed_data)} types, {page_total} members")
                    
                    # Add to aggregate counts
                    for member, count in parsed_data.items():
                        all_counts[normalize_member_designation(member)] += count
                else:
                    print("⚠️  No JSON found in response")
                    
            except Exception as page_error:
                print(f"❌ {str(page_error)[:50]}")
        
        doc.close()
        
        # Print summary
        total_members = sum(all_counts.values())
        unique_types = len(all_counts)
        print(f"\n✅ OpenAI Complete: {total_members} members, {unique_types} types")
        print("="*80)
        
        return all_counts
        
    except Exception as error:
        print(f"❌ Error: {str(error)}\n" + "="*80)
        return Counter()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: AI VISION ANALYSIS - GOOGLE GEMINI 2.0
# ══════════════════════════════════════════════════════════════════════════════

def analyze_gemini(pdf_path, api_key):
    """
    Analyze PDF with Google Gemini 2.0 Flash vision model.
    
    Provides secondary AI verification using Google's multimodal model.
    Gemini often catches different details than GPT-4O, improving overall accuracy.
    
    NOTE: Gemini is used ONLY for member verification (counts).
    It is NOT used for length determination - only OpenAI does that.
    """
    print("\n" + "="*80)
    print("🔮 STEP 3: GOOGLE GEMINI 2.0 VISION ANALYSIS")
    print("="*80)
    
    # Skip if no API key
    if not api_key:
        print("⚠️  No API key - SKIPPED\n" + "="*80)
        return Counter()
    
    print(f"🔑 API Key: {'*' * (len(api_key)-8)}{api_key[-8:]}\n")
    
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        doc = fitz.open(pdf_path)
        all_counts = Counter()
        
        # Specialized prompt for structural steel detection
        prompt = (
            'Count ALL structural steel members in this construction drawing. '
            'Return ONLY valid JSON with designations and counts. '
            'Format: {"W30X90": 12, "HSS8X8X1/2": 6}'
        )
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"📸 Page {page_num+1}: ", end="")
            
            try:
                # Convert to image
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                
                print(f"Sending {len(img_bytes):,} bytes... ", end="")
                
                # Call Gemini API
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=img_bytes, mime_type='image/png')
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=2000
                    )
                )
                
                # Parse JSON from response
                json_match = re.search(r"\{[^{}]*\}", response.text, re.DOTALL)
                
                if json_match:
                    # Clean markdown code fences if present
                    cleaned_json = re.sub(r'```(?:json)?\s*', '', json_match.group())
                    parsed_data = json.loads(cleaned_json)
                    
                    # Filter out zero counts
                    valid_members = {k: v for k, v in parsed_data.items() if v > 0}
                    page_total = sum(valid_members.values())
                    print(f"✅ Found {len(valid_members)} types, {page_total} members")
                    
                    # Aggregate counts
                    for member, count in valid_members.items():
                        all_counts[normalize_member_designation(member)] += count
                else:
                    print("⚠️  No JSON found")
                    
            except Exception as page_error:
                print(f"❌ {str(page_error)[:50]}")
        
        doc.close()
        
        # Summary
        print(f"\n✅ Gemini Complete: {sum(all_counts.values())} members, "
              f"{len(all_counts)} types")
        print("="*80)
        
        return all_counts
        
    except Exception as error:
        print(f"❌ Error: {str(error)}\n" + "="*80)
        return Counter()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: AI-POWERED LENGTH DETERMINATION (NEW!)
# ══════════════════════════════════════════════════════════════════════════════

def determine_lengths_with_ai(pdf_path, members_list, openai_key):
    """
    Use GPT-4O Vision to determine actual beam lengths from the drawing.
    
    This is the KEY IMPROVEMENT for accuracy! Instead of using default lengths,
    we ask AI to analyze the drawing and determine actual spans.
    
    IMPORTANT: This function uses OPENAI ONLY. Gemini is not involved in length
    determination - it only verifies member counts in the analyze_gemini() function.
    
    Args:
        pdf_path (str): Path to PDF
        members_list (list): List of unique member designations
        openai_key (str): OpenAI API key (Gemini is NOT used here)
    
    Returns:
        dict: {member_designation: length_in_feet}
    """
    print("\n" + "="*80)
    print("📏 STEP 4: AI-POWERED LENGTH DETERMINATION")
    print("="*80)
    
    if not openai_key:
        print("⚠️  No OpenAI key - Using default lengths\n" + "="*80)
        return {}
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        doc = fitz.open(pdf_path)
        
        # Convert first page to image (usually the main framing plan)
        page = doc[0]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        
        doc.close()
        
        # Build member list for prompt
        member_str = "\n".join([f"- {m}" for m in members_list])
        
        prompt = f"""You are a Senior Structural Steel Estimator analyzing a structural framing plan.

I have detected these steel members on the drawing:
{member_str}

YOUR TASK: Determine the ACTUAL LENGTH of each member type in feet.

CRITICAL RULES:
1. Values like "( 20' - 0" ) ± (VIF)" are TOP OF STEEL ELEVATIONS, NOT lengths!
2. Determine lengths by looking at which GRID LINES the beams span between
3. Use the DIMENSION STRINGS shown between grids (like "9'-5 1/4\"", "11'-6\"")
4. Beams typically span between column grid lines
5. For columns/posts, use 0 as they are vertical (no horizontal length)
6. If multiple lengths exist for one size, provide the most common length

RETURN JSON ONLY (no markdown, no explanation):
{{
  "W8X10": 11.0,
  "HSS8X4X5/16": 9.5,
  "W24X55": 26.0
}}

Analyze the structural drawing image and provide accurate lengths in feet."""

        print("🤖 Sending drawing to GPT-4O for length analysis...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": "high"
                        }
                    }
                ]
            }],
            max_tokens=2048,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content
        
        # Parse JSON from response
        try:
            # Try direct parse
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                print("  ⚠️ Could not parse AI response as JSON")
                return {}
        
        print(f"✅ AI determined lengths for {len(result)} member types:")
        for member, length in result.items():
            print(f"   {member}: {length} ft")
        
        print("="*80)
        return result
        
    except Exception as e:
        print(f"❌ AI length determination failed: {str(e)}")
        print("="*80)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: DIMENSION DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def find_dimensions(text_items):
    """
    Extract dimension annotations from PDF text items.
    
    Identifies dimension callouts in architectural/structural drawings.
    Used to highlight dimensions in yellow on output PDF for verification.
    """
    dimensions = []
    
    # Regex patterns for common dimension formats
    patterns = [
        r'(\d+)\s*[\'"]\s*[-–]\s*(\d+)\s*["\']',  # 24'-6"
        r'(\d+)\s*[\'"]'                            # 30'
    ]
    
    for item in text_items:
        for pattern in patterns:
            match = re.search(pattern, item['text'])
            if match:
                try:
                    # Extract feet value
                    feet_value = float(match.group(1))
                    
                    # Filter reasonable building dimensions (1-200 feet)
                    if 1 <= feet_value <= 200:
                        dimensions.append({
                            'text': item['text'],
                            'value_ft': feet_value,
                            'x': item['x'],
                            'y': item['y'],
                            'page': item['page']
                        })
                        break  # Only match once per text item
                except (ValueError, IndexError):
                    continue
    
    return dimensions


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: RECONCILIATION ENGINE WITH AI LENGTHS
# ══════════════════════════════════════════════════════════════════════════════

def reconcile(ocr_data, openai_counts, gemini_counts, ai_lengths=None):
    """
    Reconcile OCR and AI results into final material takeoff WITH AI-determined lengths.
    
    This combines three data sources with weighted confidence scoring AND
    uses AI-determined lengths instead of defaults.
    
    Decision Logic:
        1. OCR Found + AI Confirms → 95% confidence (OCR+AI)
        2. OCR Only → 90% confidence (OCR)
        3. Both AIs Agree → 80% confidence (AI weighted average)
        4. OpenAI Only → 75% confidence
        5. Gemini Only → 70% confidence
    
    Length Logic (NEW):
        1. If AI provided length → Use AI length (from OpenAI only)
        2. Else → Use category default
    
    NOTE: Gemini is used for member count verification only.
    Length determination comes from OpenAI (ai_lengths parameter).
    
    Args:
        ocr_data (dict): Results from extract_ocr()
        openai_counts (Counter): Results from analyze_openai() - used for members AND lengths
        gemini_counts (Counter): Results from analyze_gemini() - used for member verification ONLY
        ai_lengths (dict): AI-determined lengths {member: length_ft} from OpenAI
    
    Returns:
        list: Sorted list of member dictionaries with lengths
    """
    print("\n" + "="*80)
    print("⚙️  STEP 5: RECONCILING WITH AI LENGTHS")
    print("="*80)
    
    # Collect all unique member designations
    all_members = set()
    for category_counter in ocr_data["counts"].values():
        all_members.update(category_counter.keys())
    all_members.update(openai_counts.keys())
    all_members.update(gemini_counts.keys())
    
    print(f"Processing {len(all_members)} unique members\n")
    
    # Extract dimensions for highlighting
    dimensions = find_dimensions(ocr_data.get("text_items", []))
    print(f"Found {len(dimensions)} dimensions for highlighting")
    
    # Default lengths by category (used if AI doesn't provide)
    DEFAULT_LENGTHS = {
        "HSS": 15.0,
        "Joist": 30.0,
        "Beam": 25.0,
        "Channel": 20.0,
        "Angle": 20.0
    }
    
    # Use AI lengths if provided
    if ai_lengths:
        print(f"Using AI-determined lengths for {len(ai_lengths)} members\n")
    
    results = []
    
    # Process each member
    for idx, member in enumerate(all_members, 1):
        # Get counts from each source
        ocr_count = sum(
            category_counts.get(member, 0)
            for category_counts in ocr_data["counts"].values()
        )
        openai_count = openai_counts.get(member, 0)
        gemini_count = gemini_counts.get(member, 0)
        
        # Determine category
        category = categorize_member(member)
        if category == "Other":
            continue  # Skip unrecognized members
        
        # DECISION LOGIC - Determine final count and confidence
        if ocr_count > 0:
            final_count = ocr_count
            confidence = 0.90
            method = "OCR"
            
            # Check if AI confirms
            ai_average = (openai_count + gemini_count) / 2 if (openai_count + gemini_count) > 0 else 0
            if ai_average > 0:
                variance = abs(ocr_count - ai_average) / max(ocr_count, ai_average)
                if variance < 0.3:
                    confidence = 0.95
                    method = "OCR+AI"
        
        elif openai_count > 0 or gemini_count > 0:
            if openai_count > 0 and gemini_count > 0:
                final_count = int(round(openai_count * 0.6 + gemini_count * 0.4))
                confidence = 0.80
                method = "AI"
            elif openai_count > 0:
                final_count = openai_count
                confidence = 0.75
                method = "OpenAI"
            else:
                final_count = gemini_count
                confidence = 0.70
                method = "Gemini"
        else:
            continue
        
        # ══════════════════════════════════════════════════════════
        # LENGTH DETERMINATION - AI First, then Default
        # ══════════════════════════════════════════════════════════
        if ai_lengths and member in ai_lengths:
            # Use AI-determined length
            length_ft = ai_lengths[member]
            length_source = "AI Vision"
        else:
            # Use category default
            length_ft = DEFAULT_LENGTHS.get(category, 20.0)
            length_source = "Default"
        
        # Calculate tonnage
        weight_per_ft = lookup_member_weight(member)
        total_length = final_count * length_ft
        total_weight = total_length * weight_per_ft
        
        # Build result record
        results.append({
            "designation": member,
            "category": category,
            "quantity": final_count,
            "weight_per_ft": weight_per_ft,
            "length_ft": length_ft,
            "length_source": length_source,
            "total_length": total_length,
            "total_weight": total_weight,
            "confidence": confidence,
            "method": method,
            "ocr_count": ocr_count,
            "openai_count": openai_count,
            "gemini_count": gemini_count,
            "positions": ocr_data["positions"].get(member, []),
        })
        
        # Progress indicator
        if idx % 10 == 0:
            print(f"  Processed {idx}/{len(all_members)} members...")
    
    # Sort by total weight (heaviest first)
    results.sort(key=lambda x: x["total_weight"], reverse=True)
    
    # Print summary
    total_members = sum(r['quantity'] for r in results)
    total_weight = sum(r['total_weight'] for r in results)
    ai_length_count = sum(1 for r in results if r['length_source'] == 'AI Vision')
    
    print(f"\n✅ Reconciliation Complete:")
    print(f"   Final Members: {total_members}")
    print(f"   Unique Types: {len(results)}")
    print(f"   Total Weight: {total_weight:,.0f} lbs")
    print(f"   AI Lengths Used: {ai_length_count}/{len(results)}")
    print("="*80)
    
    return results


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: PDF VISUALIZATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def create_highlighted_pdf(pdf_path, results, output_path, text_items=None):
    """
    Generate color-coded PDF with member and dimension highlights.
    
    Creates visual verification document showing:
    - GREEN: W-beams
    - ORANGE: HSS tubes
    - MAGENTA: Channels
    - CYAN: Angles
    - YELLOW-GREEN: Joists
    - YELLOW: Dimensions
    """
    print("\n📄 Creating highlighted PDF...")
    
    doc = fitz.open(pdf_path)
    
    # Color scheme by category
    colors = {
        "Beam": (0, 0.7, 0),
        "HSS": (0.9, 0.5, 0),
        "Channel": (0.8, 0, 0.8),
        "Angle": (0, 0.8, 0.8),
        "Joist": (0.8, 0.8, 0)
    }
    
    # Highlight Steel Members
    member_highlight_count = 0
    
    for result in results:
        category_color = colors.get(result["category"], (0.5, 0.5, 0.5))
        
        for position in result["positions"]:
            page_num = position["page"]
            
            if page_num < len(doc):
                page = doc[page_num]
                
                try:
                    bbox_rect = fitz.Rect(position["bbox"])
                    highlight_rect = bbox_rect + (-2, -2, 2, 2)
                    
                    page.draw_rect(
                        highlight_rect,
                        color=category_color,
                        fill=category_color,
                        width=1,
                        fill_opacity=0.3
                    )
                    member_highlight_count += 1
                    
                except Exception:
                    pass
    
    # Highlight Dimensions in YELLOW
    dimension_highlight_count = 0
    
    if text_items:
        dimensions = find_dimensions(text_items)
        print(f"  Highlighting {len(dimensions)} dimensions in yellow...")
        
        for dim in dimensions:
            page_num = dim['page']
            
            if page_num < len(doc):
                page = doc[page_num]
                
                try:
                    x, y = dim['x'], dim['y']
                    highlight_rect = fitz.Rect(x - 30, y - 8, x + 30, y + 8)
                    
                    page.draw_rect(
                        highlight_rect,
                        color=(1, 1, 0),
                        fill=(1, 1, 0),
                        width=1,
                        fill_opacity=0.4
                    )
                    dimension_highlight_count += 1
                    
                except Exception:
                    pass
    
    # Add Legend
    if len(doc) > 0:
        first_page = doc[0]
        
        legend_text = f"""MATERIAL TAKEOFF VISUALIZATION
{'='*40}
• BEAMS: Green
• HSS: Orange  
• CHANNELS: Magenta
• ANGLES: Cyan
• JOISTS: Yellow-Green
• DIMENSIONS: Yellow

Members Highlighted: {member_highlight_count}
Dimensions Highlighted: {dimension_highlight_count}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        legend_box = fitz.Rect(10, 10, 280, 160)
        
        first_page.draw_rect(
            legend_box,
            color=(0, 0, 0),
            fill=(1, 1, 0.9),
            width=2
        )
        
        first_page.insert_textbox(
            legend_box,
            legend_text,
            fontsize=8,
            fontname="helv",
            color=(0, 0, 0)
        )
    
    doc.save(output_path)
    doc.close()
    
    print(f"✅ Saved: {os.path.basename(output_path)}")
    print(f"   Members highlighted: {member_highlight_count}")
    print(f"   Dimensions highlighted: {dimension_highlight_count}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10: EXCEL REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def create_excel(results, output_path, pdf_path):
    """
    Generate professional Excel takeoff report with summary sheet.
    
    Creates two-sheet workbook with detailed takeoff and summary statistics.
    """
    print("📊 Creating Excel report...")
    
    # Build Takeoff Sheet Data
    takeoff_rows = []
    
    for result in results:
        takeoff_rows.append({
            "Designation": result["designation"],
            "Category": result["category"],
            "Quantity": result["quantity"],
            "Weight (lbs/ft)": result["weight_per_ft"],
            "Length (ft)": result["length_ft"],
            "Length Source": result.get("length_source", "Default"),
            "Total Length (ft)": result["total_length"],
            "Total Weight (lbs)": result["total_weight"],
            "Confidence": f"{result['confidence']*100:.0f}%",
            "Method": result["method"],
            "OCR": result["ocr_count"],
            "OpenAI": result["openai_count"],
            "Gemini": result["gemini_count"],
        })
    
    takeoff_df = pd.DataFrame(takeoff_rows)
    
    # Build Summary Sheet
    total_weight_lbs = takeoff_df["Total Weight (lbs)"].sum()
    total_weight_tons = total_weight_lbs / 2000
    ai_length_count = len([r for r in results if r.get("length_source") == "AI Vision"])
    
    summary_df = pd.DataFrame({
        "Metric": [
            "File",
            "Total Members",
            "Types",
            "Weight (lbs)",
            "Weight (tons)",
            "AI Lengths Used",
            "Date"
        ],
        "Value": [
            os.path.basename(pdf_path),
            takeoff_df["Quantity"].sum(),
            len(takeoff_df),
            f"{total_weight_lbs:,.0f}",
            f"{total_weight_tons:.2f}",
            f"{ai_length_count}/{len(results)}",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ],
    })
    
    # Write Excel File
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        takeoff_df.to_excel(writer, sheet_name="Takeoff", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
    
    print(f"✅ Saved: {os.path.basename(output_path)}")


# ══════════════════════════════════════════════════════════════════════════════
# END OF CORE.PY
# ══════════════════════════════════════════════════════════════════════════════