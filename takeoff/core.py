"""
Material Takeoff Core Logic - FIXED VERSION
Added detailed error logging to diagnose AI API failures
"""

import os
import re
import json
import base64
from io import BytesIO
from collections import Counter, defaultdict
from datetime import datetime
import fitz
import pandas as pd
from PIL import Image

# Steel weights database (unchanged)
STEEL_WEIGHTS = {
    "W44X335": 335, "W44X290": 290, "W40X593": 593, "W40X503": 503,
    "W36X798": 798, "W36X650": 650, "W36X527": 527, "W36X393": 393,
    "W36X359": 359, "W36X328": 328, "W36X300": 300, "W36X280": 280,
    "W36X260": 260, "W36X245": 245, "W36X230": 230, "W36X210": 210,
    "W36X194": 194, "W36X182": 182, "W36X170": 170, "W36X160": 160,
    "W36X150": 150, "W36X135": 135, "W33X387": 387, "W33X354": 354,
    "W33X318": 318, "W33X291": 291, "W33X263": 263, "W33X241": 241,
    "W33X221": 221, "W33X201": 201, "W33X169": 169, "W33X152": 152,
    "W33X141": 141, "W33X130": 130, "W30X391": 391, "W30X357": 357,
    "W30X326": 326, "W30X292": 292, "W30X261": 261, "W30X235": 235,
    "W30X211": 211, "W30X191": 191, "W30X173": 173, "W30X148": 148,
    "W30X132": 132, "W30X124": 124, "W30X116": 116, "W30X108": 108,
    "W30X99": 99, "W30X90": 90, "W27X539": 539, "W27X368": 368,
    "W27X307": 307, "W27X281": 281, "W27X258": 258, "W27X235": 235,
    "W27X217": 217, "W27X194": 194, "W27X178": 178, "W27X161": 161,
    "W27X146": 146, "W27X129": 129, "W27X114": 114, "W27X102": 102,
    "W27X94": 94, "W27X84": 84, "W24X370": 370, "W24X335": 335,
    "W24X306": 306, "W24X279": 279, "W24X250": 250, "W24X229": 229,
    "W24X207": 207, "W24X192": 192, "W24X176": 176, "W24X162": 162,
    "W24X146": 146, "W24X131": 131, "W24X117": 117, "W24X104": 104,
    "W24X94": 94, "W24X84": 84, "W24X76": 76, "W24X68": 68,
    "W24X62": 62, "W24X55": 55, "W21X201": 201, "W21X182": 182,
    "W21X166": 166, "W21X147": 147, "W21X132": 132, "W21X122": 122,
    "W21X111": 111, "W21X101": 101, "W21X93": 93, "W21X83": 83,
    "W21X73": 73, "W21X68": 68, "W21X62": 62, "W21X55": 55,
    "W21X48": 48, "W21X44": 44, "W18X311": 311, "W18X283": 283,
    "W18X258": 258, "W18X234": 234, "W18X211": 211, "W18X192": 192,
    "W18X175": 175, "W18X158": 158, "W18X143": 143, "W18X130": 130,
    "W18X119": 119, "W18X106": 106, "W18X97": 97, "W18X86": 86,
    "W18X76": 76, "W18X71": 71, "W18X65": 65, "W18X60": 60,
    "W18X55": 55, "W18X50": 50, "W18X46": 46, "W18X40": 40,
    "W18X35": 35, "W16X100": 100, "W16X89": 89, "W16X77": 77,
    "W16X67": 67, "W16X57": 57, "W16X50": 50, "W16X45": 45,
    "W16X40": 40, "W16X36": 36, "W16X31": 31, "W16X26": 26,
    "W14X730": 730, "W14X665": 665, "W14X605": 605, "W14X550": 550,
    "W14X500": 500, "W14X455": 455, "W14X426": 426, "W14X398": 398,
    "W14X370": 370, "W14X342": 342, "W14X311": 311, "W14X283": 283,
    "W14X257": 257, "W14X233": 233, "W14X211": 211, "W14X193": 193,
    "W14X176": 176, "W14X159": 159, "W14X145": 145, "W14X132": 132,
    "W14X120": 120, "W14X109": 109, "W14X99": 99, "W14X90": 90,
    "W14X82": 82, "W14X74": 74, "W14X68": 68, "W14X61": 61,
    "W14X53": 53, "W14X48": 48, "W14X43": 43, "W14X38": 38,
    "W14X34": 34, "W14X30": 30, "W14X26": 26, "W14X22": 22,
    "W12X336": 336, "W12X305": 305, "W12X279": 279, "W12X252": 252,
    "W12X230": 230, "W12X210": 210, "W12X190": 190, "W12X170": 170,
    "W12X152": 152, "W12X136": 136, "W12X120": 120, "W12X106": 106,
    "W12X96": 96, "W12X87": 87, "W12X79": 79, "W12X72": 72,
    "W12X65": 65, "W12X58": 58, "W12X53": 53, "W12X50": 50,
    "W12X45": 45, "W12X40": 40, "W12X35": 35, "W12X30": 30,
    "W12X26": 26, "W12X22": 22, "W12X19": 19, "W12X16": 16,
    "W12X14": 14, "W10X112": 112, "W10X100": 100, "W10X88": 88,
    "W10X77": 77, "W10X68": 68, "W10X60": 60, "W10X54": 54,
    "W10X49": 49, "W10X45": 45, "W10X39": 39, "W10X33": 33,
    "W10X30": 30, "W10X26": 26, "W10X22": 22, "W10X19": 19,
    "W10X17": 17, "W10X15": 15, "W10X12": 12, "W8X67": 67,
    "W8X58": 58, "W8X48": 48, "W8X40": 40, "W8X35": 35,
    "W8X31": 31, "W8X28": 28, "W8X24": 24, "W8X21": 21,
    "W8X18": 18, "W8X15": 15, "W8X13": 13, "W8X10": 10,
    "W6X25": 25, "W6X20": 20, "W6X15": 15, "W6X16": 16,
    "W6X12": 12, "W6X9": 9, "W5X19": 19, "W5X16": 16, "W4X13": 13,
    "HSS20X12X5/8": 93.34, "HSS16X16X5/8": 93.34, "HSS14X14X5/8": 82.31,
    "HSS12X12X5/8": 71.28, "HSS12X12X1/2": 58.15, "HSS12X12X3/8": 44.59,
    "HSS10X10X5/8": 60.25, "HSS10X10X1/2": 49.19, "HSS10X10X3/8": 37.82,
    "HSS10X10X5/16": 31.84, "HSS10X10X1/4": 25.82, "HSS8X8X5/8": 48.86,
    "HSS8X8X1/2": 40.23, "HSS8X8X3/8": 31.05, "HSS8X8X5/16": 26.21,
    "HSS8X8X1/4": 21.28, "HSS6X6X5/8": 38.47, "HSS6X6X1/2": 31.76,
    "HSS6X6X3/8": 24.28, "HSS6X6X5/16": 20.57, "HSS6X6X1/4": 16.74,
    "HSS5X5X1/2": 26.30, "HSS5X5X3/8": 20.51, "HSS5X5X1/4": 14.21,
    "HSS4X4X1/2": 21.36, "HSS4X4X3/8": 16.74, "HSS4X4X1/4": 11.68,
    "C15X50": 50, "C15X40": 40, "C12X30": 30, "C12X25": 25,
    "C10X30": 30, "C10X25": 25, "C10X20": 20, "C8X18.75": 18.75,
    "C8X13.75": 13.75, "C8X11.5": 11.5, "MC12X50": 50, "MC12X40": 40,
    "L8X8X1": 51.0, "L6X6X3/4": 28.7, "L6X6X1/2": 19.6,
    "L4X4X1/2": 12.8, "L4X4X3/8": 9.8, "L3X3X3/8": 7.2,
}

# Patterns (unchanged)
W_BEAM = re.compile(r"W\d+[xX]\d+", re.IGNORECASE)
HSS = re.compile(r"HSS\d+[xX]\d+[xX][\d/]+", re.IGNORECASE)
CHANNEL = re.compile(r"(?:MC|C)\d+[xX][\d.]+", re.IGNORECASE)
ANGLE = re.compile(r"L\d+[xX]\d+[xX][\d/]+", re.IGNORECASE)
JOIST = re.compile(r"\d{2}[KLH]+\d+", re.IGNORECASE)


def normalize(m):
    n = m.upper()
    n = re.sub(r"(?<=[0-9])x(?=[0-9])", "X", n)
    return re.sub(r"\s+", "", n)


def get_category(m):
    m = m.upper()
    if m.startswith("W") and "X" in m:
        return "Beam"
    if m.startswith("HSS"):
        return "HSS"
    if m.startswith(("C", "MC")) and "X" in m:
        return "Channel"
    if m.startswith("L") and m.count("X") >= 2:
        return "Angle"
    if re.match(r"\d{2}[KLH]", m):
        return "Joist"
    return "Other"


def get_weight(member):
    if member in STEEL_WEIGHTS:
        return STEEL_WEIGHTS[member]
    if member.startswith("W"):
        match = re.search(r"X(\d+)", member)
        if match:
            return float(match.group(1))
    return 25.0


def extract_ocr(pdf_path):
    """OCR Extraction - unchanged"""
    doc = fitz.open(pdf_path)
    counts = {
        "beams": Counter(),
        "hss": Counter(),
        "channels": Counter(),
        "angles": Counter(),
        "joists": Counter(),
    }
    positions = defaultdict(list)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        for match in W_BEAM.finditer(text):
            counts["beams"][normalize(match.group())] += 1
        for match in HSS.finditer(text):
            counts["hss"][normalize(match.group())] += 1
        for match in CHANNEL.finditer(text):
            counts["channels"][normalize(match.group())] += 1
        for match in ANGLE.finditer(text):
            counts["angles"][normalize(match.group())] += 1
        for match in JOIST.finditer(text):
            counts["joists"][normalize(match.group())] += 1

        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        for pattern in [W_BEAM, HSS, CHANNEL, ANGLE, JOIST]:
                            for match in pattern.finditer(span["text"]):
                                positions[normalize(match.group())].append(
                                    {"page": page_num, "bbox": span["bbox"]}
                                )
    doc.close()
    return {"counts": counts, "positions": dict(positions)}


def analyze_openai(pdf_path, api_key):
    """OpenAI Analysis - FIXED with detailed error logging"""
    if not api_key:
        print("   ⚠️ OpenAI: No API key provided")
        return Counter()
    
    print(f"   🔑 OpenAI: API key present (length: {len(api_key)})")
    
    try:
        from openai import OpenAI
        
        print("   📦 OpenAI: Module imported successfully")
        
        # Test API key validity
        try:
            client = OpenAI(api_key=api_key)
            print("   ✅ OpenAI: Client created successfully")
        except Exception as e:
            print(f"   ❌ OpenAI: Client creation failed: {str(e)}")
            return Counter()
        
        doc = fitz.open(pdf_path)
        all_counts = Counter()
        total_pages = len(doc)
        
        print(f"   📄 OpenAI: Processing {total_pages} pages...")

        for page_num in range(total_pages):
            page = doc[page_num]
            
            try:
                # Render page to image
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                
                print(f"   📸 OpenAI: Page {page_num+1} rendered ({len(img_b64):,} chars base64)")
                
                # Make API call
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": 'Count ALL structural steel members. Return ONLY JSON: {"W30X90": 81}',
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.1,
                )
                
                content = resp.choices[0].message.content
                print(f"   💬 OpenAI: Page {page_num+1} response received ({len(content)} chars)")
                print(f"   📝 OpenAI: Response preview: {content[:200]}...")
                
                # Parse JSON from response
                json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    print(f"   ✅ OpenAI: Page {page_num+1} parsed {len(parsed)} items")
                    for k, v in parsed.items():
                        all_counts[normalize(k)] += v
                else:
                    print(f"   ⚠️ OpenAI: Page {page_num+1} - no JSON found in response")
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ OpenAI: Page {page_num+1} JSON parse error: {str(e)}")
            except Exception as e:
                print(f"   ❌ OpenAI: Page {page_num+1} error: {str(e)}")
                import traceback
                print(f"   📋 Traceback: {traceback.format_exc()}")
        
        doc.close()
        print(f"   🎯 OpenAI: Total found {len(all_counts)} types, {sum(all_counts.values())} items")
        return all_counts
        
    except ImportError as e:
        print(f"   ❌ OpenAI: Module import failed: {str(e)}")
        print("   💡 Run: pip install openai")
        return Counter()
    except Exception as e:
        print(f"   ❌ OpenAI: Unexpected error: {str(e)}")
        import traceback
        print(f"   📋 Traceback: {traceback.format_exc()}")
        return Counter()


def analyze_gemini(pdf_path, api_key):
    """Gemini Analysis - FIXED with better prompt and config"""
    if not api_key:
        print("   ⚠️ Gemini: No API key provided")
        return Counter()
    
    print(f"   🔑 Gemini: API key present (length: {len(api_key)})")
    
    try:
        # Try new package first
        try:
            from google import genai
            from google.genai import types
            print("   📦 Gemini: Using NEW google-genai package")
            
            client = genai.Client(api_key=api_key)
            model_id = "gemini-2.0-flash-exp"
            print(f"   ✅ Gemini: Client configured ({model_id})")
            use_new_api = True
            
        except ImportError:
            # Fall back to old deprecated package
            import google.generativeai as genai_old
            print("   📦 Gemini: Using OLD deprecated package (update recommended)")
            
            genai_old.configure(api_key=api_key)
            model = genai_old.GenerativeModel("gemini-2.0-flash-exp")
            print("   ✅ Gemini: Model configured (gemini-2.0-flash-exp)")
            use_new_api = False

        doc = fitz.open(pdf_path)
        all_counts = Counter()
        total_pages = len(doc)
        
        print(f"   📄 Gemini: Processing {total_pages} pages...")

        for page_num in range(total_pages):
            page = doc[page_num]
            
            try:
                # Render page to image
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                
                print(f"   📸 Gemini: Page {page_num+1} rendered")
                
                # Enhanced prompt for better accuracy
                prompt = """You are analyzing a structural engineering drawing. 

TASK: Count EVERY structural steel member callout on this drawing.

MEMBER TYPES TO FIND:
- W-beams (e.g., W30X90, W27X84, W24X55)
- HSS tubes (e.g., HSS8X8X1/2)
- Channels (e.g., C12X30, MC10X25)
- Angles (e.g., L6X6X1/2)
- Joists (e.g., 24K9, 18LH06)

INSTRUCTIONS:
1. Look at ALL member callouts/labels on the drawing
2. Count EACH occurrence (if W30X90 appears 5 times, count = 5)
3. If a schedule/table shows quantities, use those numbers
4. Return ONLY valid JSON with NO extra text

EXAMPLE OUTPUT:
{"W30X90": 81, "W27X84": 34, "HSS8X8X1/2": 12}

If you find NO members, return: {}

NOW count all members in this drawing:"""
                
                # Make API call based on package version
                if use_new_api:
                    # NEW API
                    response = client.models.generate_content(
                        model=model_id,
                        contents=[
                            prompt,
                            types.Part.from_bytes(
                                data=img_bytes,
                                mime_type='image/png'
                            )
                        ],
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=2000,
                        )
                    )
                    content = response.text
                else:
                    # Old API (deprecated)
                    img = Image.open(BytesIO(img_bytes))
                    generation_config = {
                        'temperature': 0.1,
                        'max_output_tokens': 2000,
                    }
                    resp = model.generate_content(
                        [prompt, img],
                        generation_config=generation_config
                    )
                    content = resp.text
                    
                print(f"   💬 Gemini: Page {page_num+1} response received ({len(content)} chars)")
                print(f"   📝 Gemini: Response preview: {content[:300]}...")
                
                # Parse JSON from response - handle multiple formats
                json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Clean up common JSON issues
                    json_str = re.sub(r'```json\s*', '', json_str)
                    json_str = re.sub(r'```\s*', '', json_str)
                    
                    parsed = json.loads(json_str)
                    
                    # Filter out zero counts
                    valid_items = {k: v for k, v in parsed.items() if v > 0}
                    
                    if valid_items:
                        print(f"   ✅ Gemini: Page {page_num+1} parsed {len(valid_items)} items with counts")
                        for k, v in valid_items.items():
                            all_counts[normalize(k)] += v
                    else:
                        print(f"   ⚠️ Gemini: Page {page_num+1} - all counts were 0")
                else:
                    print(f"   ⚠️ Gemini: Page {page_num+1} - no JSON found in response")
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ Gemini: Page {page_num+1} JSON parse error: {str(e)}")
                print(f"   📄 Raw response: {content}")
            except Exception as e:
                print(f"   ❌ Gemini: Page {page_num+1} error: {str(e)}")
                import traceback
                print(f"   📋 Traceback: {traceback.format_exc()}")
        
        doc.close()
        print(f"   🎯 Gemini: Total found {len(all_counts)} types, {sum(all_counts.values())} items")
        return all_counts
        
    except ImportError as e:
        print(f"   ❌ Gemini: Module import failed: {str(e)}")
        print("   💡 Run: pip install google-genai")
        return Counter()
    except Exception as e:
        print(f"   ❌ Gemini: Unexpected error: {str(e)}")
        import traceback
        print(f"   📋 Traceback: {traceback.format_exc()}")
        return Counter()
        
def reconcile(ocr_data, openai_counts, gemini_counts):
    """Reconcile Results - unchanged"""
    all_members = set()
    for c in ocr_data["counts"].values():
        all_members.update(c.keys())
    all_members.update(openai_counts.keys())
    all_members.update(gemini_counts.keys())

    results = []
    for member in all_members:
        ocr_count = sum(c.get(member, 0) for c in ocr_data["counts"].values())
        openai_count = openai_counts.get(member, 0)
        gemini_count = gemini_counts.get(member, 0)

        category = get_category(member)
        if category == "Other":
            continue

        if ocr_count > 0:
            final_count, confidence, method = ocr_count, 0.90, "OCR (Primary)"
            ai_avg = (
                (openai_count + gemini_count) / 2
                if (openai_count + gemini_count) > 0
                else 0
            )
            if ai_avg > 0 and abs(ocr_count - ai_avg) / max(ocr_count, ai_avg) < 0.3:
                confidence, method = 0.95, "OCR + AI Verified"
        elif openai_count > 0 or gemini_count > 0:
            if openai_count > 0 and gemini_count > 0:
                final_count, confidence, method = (
                    int(round(openai_count * 0.6 + gemini_count * 0.4)),
                    0.80,
                    "AI Consensus",
                )
            elif openai_count > 0:
                final_count, confidence, method = openai_count, 0.75, "OpenAI Only"
            else:
                final_count, confidence, method = gemini_count, 0.70, "Gemini Only"
        else:
            continue

        weight = get_weight(member)
        length = 15.0 if category == "HSS" else (30.0 if category == "Joist" else 25.0)

        results.append(
            {
                "designation": member,
                "category": category,
                "quantity": final_count,
                "weight_per_ft": weight,
                "length_ft": length,
                "total_length": final_count * length,
                "total_weight": final_count * length * weight,
                "confidence": confidence,
                "method": method,
                "ocr_count": ocr_count,
                "openai_count": openai_count,
                "gemini_count": gemini_count,
                "positions": ocr_data["positions"].get(member, []),
            }
        )

    results.sort(key=lambda x: x["total_weight"], reverse=True)
    return results


def create_highlighted_pdf(pdf_path, results, output_path):
    """Create Highlighted PDF - unchanged"""
    doc = fitz.open(pdf_path)
    colors = {
        "Beam": (0, 0.7, 0),
        "HSS": (0.9, 0.5, 0),
        "Channel": (0.8, 0, 0.8),
        "Angle": (0, 0.8, 0.8),
        "Joist": (0.8, 0.8, 0),
    }
    highlight_counts = Counter()

    for r in results:
        color = colors.get(r["category"], (0.5, 0.5, 0.5))
        for pos in r["positions"]:
            if pos["page"] < len(doc):
                page = doc[pos["page"]]
                try:
                    rect = fitz.Rect(pos["bbox"]) + (-2, -2, 2, 2)
                    annot = page.add_rect_annot(rect)
                    annot.set_colors(stroke=color)
                    annot.set_border(width=1.5)
                    annot.update()
                    highlight_counts[r["category"]] += 1
                except:
                    pass

    total_members = sum(r["quantity"] for r in results)
    total_weight = sum(r["total_weight"] for r in results)
    legend = f"MATERIAL TAKEOFF v1.0\n{'='*30}\nMembers: {total_members}\nTypes: {len(results)}\nWeight: {total_weight:,.0f} lbs\n\nHighlights:\n"
    for cat, cnt in highlight_counts.most_common():
        legend += f"  {cat}: {cnt}\n"

    doc[0].insert_textbox(
        fitz.Rect(10, 10, 250, 160),
        legend,
        fontsize=9,
        fontname="helv",
        color=(0, 0, 0),
        fill=(1, 1, 0.9),
        border_width=1,
    )
    doc.save(output_path)
    doc.close()


def create_excel(results, output_path, pdf_path):
    """Create Excel - unchanged"""
    rows = [
        {
            "Designation": r["designation"],
            "Category": r["category"],
            "Quantity": r["quantity"],
            "Weight (lbs/ft)": r["weight_per_ft"],
            "Length (ft)": r["length_ft"],
            "Total Length (ft)": r["total_length"],
            "Total Weight (lbs)": r["total_weight"],
            "Confidence": f"{r['confidence']*100:.0f}%",
            "Method": r["method"],
            "OCR": r["ocr_count"],
            "OpenAI": r["openai_count"],
            "Gemini": r["gemini_count"],
        }
        for r in results
    ]

    df = pd.DataFrame(rows)
    summary = pd.DataFrame(
        {
            "Metric": [
                "File",
                "Total Members",
                "Types",
                "Weight (lbs)",
                "Weight (tons)",
                "Date",
                "Version",
            ],
            "Value": [
                os.path.basename(pdf_path),
                df["Quantity"].sum(),
                len(df),
                f"{df['Total Weight (lbs)'].sum():,.0f}",
                f"{df['Total Weight (lbs)'].sum()/2000:.2f}",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "SaaS v1.0",
            ],
        }
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Takeoff", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)