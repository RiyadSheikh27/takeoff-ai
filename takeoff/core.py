"""
Material Takeoff Core Logic - VERBOSE CONSOLE OUTPUT VERSION
Matches the detailed logging from the working Jupyter notebook
"""

import os
import re
import json
import base64
import math
from io import BytesIO
from collections import Counter, defaultdict
from datetime import datetime
import fitz
import pandas as pd
from PIL import Image

# [Previous STEEL_WEIGHTS and patterns remain the same - truncated for brevity]
STEEL_WEIGHTS = {
    "W30X90": 90, "W27X84": 84, "W24X55": 55, "W18X35": 35,
    "HSS8X8X1/2": 40.23, "C12X30": 30, "L6X6X1/2": 19.6,
    # ... (keep your full database)
}

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
    if m.startswith("W") and "X" in m: return "Beam"
    if m.startswith("HSS"): return "HSS"
    if m.startswith(("C", "MC")) and "X" in m: return "Channel"
    if m.startswith("L") and m.count("X") >= 2: return "Angle"
    if re.match(r"\d{2}[KLH]", m): return "Joist"
    return "Other"

def get_weight(member):
    if member in STEEL_WEIGHTS: return STEEL_WEIGHTS[member]
    if member.startswith("W"):
        match = re.search(r"X(\d+)", member)
        if match: return float(match.group(1))
    return 25.0


def extract_ocr(pdf_path):
    """OCR Extraction - VERBOSE VERSION"""
    print("\n" + "="*80)
    print("📄 STEP 1: OCR TEXT EXTRACTION")
    print("="*80)
    print(f"File: {os.path.basename(pdf_path)}\n")
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"📖 Total pages: {total_pages}")
    
    counts = {
        "beams": Counter(), "hss": Counter(), "channels": Counter(),
        "angles": Counter(), "joists": Counter(),
    }
    positions = defaultdict(list)
    all_text_items = []

    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        
        page_counts = {"beams": 0, "hss": 0, "channels": 0, "angles": 0, "joists": 0}
        
        for match in W_BEAM.finditer(text):
            member = normalize(match.group())
            counts["beams"][member] += 1
            page_counts["beams"] += 1
            
        for match in HSS.finditer(text):
            member = normalize(match.group())
            counts["hss"][member] += 1
            page_counts["hss"] += 1
            
        for match in CHANNEL.finditer(text):
            member = normalize(match.group())
            counts["channels"][member] += 1
            page_counts["channels"] += 1
            
        for match in ANGLE.finditer(text):
            member = normalize(match.group())
            counts["angles"][member] += 1
            page_counts["angles"] += 1
            
        for match in JOIST.finditer(text):
            member = normalize(match.group())
            counts["joists"][member] += 1
            page_counts["joists"] += 1

        print(f"  Page {page_num+1}: Beams={page_counts['beams']}, HSS={page_counts['hss']}, " +
              f"Channels={page_counts['channels']}, Angles={page_counts['angles']}, Joists={page_counts['joists']}")

        # Get positioned text
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if span_text and len(span_text) > 1:
                            bbox = span["bbox"]
                            all_text_items.append({
                                'text': span_text, 'x': (bbox[0] + bbox[2]) / 2,
                                'y': (bbox[1] + bbox[3]) / 2, 'bbox': bbox, 'page': page_num,
                            })
                            
                        for pattern in [W_BEAM, HSS, CHANNEL, ANGLE, JOIST]:
                            for match in pattern.finditer(span["text"]):
                                positions[normalize(match.group())].append(
                                    {"page": page_num, "bbox": span["bbox"]}
                                )
    
    doc.close()
    
    total = sum(sum(c.values()) for c in counts.values())
    print(f"\n✅ OCR Complete: {total} members found")
    print(f"   Beams: {sum(counts['beams'].values())}")
    print(f"   HSS: {sum(counts['hss'].values())}")
    print(f"   Channels: {sum(counts['channels'].values())}")
    print(f"   Angles: {sum(counts['angles'].values())}")
    print(f"   Joists: {sum(counts['joists'].values())}")
    print("="*80)
    
    return {"counts": counts, "positions": dict(positions), "text_items": all_text_items}


def analyze_openai(pdf_path, api_key):
    """OpenAI Analysis - VERBOSE VERSION"""
    print("\n" + "="*80)
    print("🤖 STEP 2: OPENAI GPT-4O VISION ANALYSIS")
    print("="*80)
    
    if not api_key:
        print("⚠️  No API key - SKIPPED\n" + "="*80)
        return Counter()
    
    print(f"🔑 API Key: {'*' * (len(api_key)-8)}{api_key[-8:]}\n")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        doc = fitz.open(pdf_path)
        all_counts = Counter()
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"📸 Page {page_num+1}: ", end="")
            
            try:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                
                print(f"Sending {len(img_bytes):,} bytes... ", end="")
                
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": 'Count ALL structural steel members. Return ONLY JSON: {"W30X90": 81}'},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}},
                        ],
                    }],
                    max_tokens=2000,
                    temperature=0.1,
                )
                
                content = resp.choices[0].message.content
                json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                
                if json_match:
                    parsed = json.loads(json_match.group())
                    page_total = sum(parsed.values())
                    print(f"✅ Found {len(parsed)} types, {page_total} members")
                    for k, v in parsed.items():
                        all_counts[normalize(k)] += v
                else:
                    print("⚠️  No JSON")
                    
            except Exception as e:
                print(f"❌ {str(e)[:50]}")
        
        doc.close()
        print(f"\n✅ OpenAI Complete: {sum(all_counts.values())} members, {len(all_counts)} types")
        print("="*80)
        return all_counts
        
    except Exception as e:
        print(f"❌ Error: {str(e)}\n" + "="*80)
        return Counter()


def analyze_gemini(pdf_path, api_key):
    """Gemini Analysis - VERBOSE VERSION"""
    print("\n" + "="*80)
    print("🔮 STEP 3: GOOGLE GEMINI 2.0 VISION ANALYSIS")
    print("="*80)
    
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
        
        prompt = 'Count ALL structural steel members. Return ONLY JSON: {"W30X90": 81}'
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            print(f"📸 Page {page_num+1}: ", end="")
            
            try:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                
                print(f"Sending {len(img_bytes):,} bytes... ", end="")
                
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type='image/png')],
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=2000)
                )
                
                json_match = re.search(r"\{[^{}]*\}", response.text, re.DOTALL)
                if json_match:
                    parsed = json.loads(re.sub(r'```(?:json)?\s*', '', json_match.group()))
                    valid = {k: v for k, v in parsed.items() if v > 0}
                    page_total = sum(valid.values())
                    print(f"✅ Found {len(valid)} types, {page_total} members")
                    for k, v in valid.items():
                        all_counts[normalize(k)] += v
                else:
                    print("⚠️  No JSON")
                    
            except Exception as e:
                print(f"❌ {str(e)[:50]}")
        
        doc.close()
        print(f"\n✅ Gemini Complete: {sum(all_counts.values())} members, {len(all_counts)} types")
        print("="*80)
        return all_counts
        
    except Exception as e:
        print(f"❌ Error: {str(e)}\n" + "="*80)
        return Counter()


def reconcile(ocr_data, openai_counts, gemini_counts):
    """Reconcile Results - VERBOSE VERSION"""
    print("\n" + "="*80)
    print("⚙️  STEP 4: RECONCILING & FINALIZING")
    print("="*80)
    
    all_members = set()
    for c in ocr_data["counts"].values():
        all_members.update(c.keys())
    all_members.update(openai_counts.keys())
    all_members.update(gemini_counts.keys())
    
    print(f"Processing {len(all_members)} unique members\n")
    
    # Find dimensions for reporting
    dimensions = find_dimensions(ocr_data.get("text_items", []))
    print(f"Found {len(dimensions)} dimensions for highlighting")

    results = []
    for i, member in enumerate(all_members, 1):
        ocr_count = sum(c.get(member, 0) for c in ocr_data["counts"].values())
        openai_count = openai_counts.get(member, 0)
        gemini_count = gemini_counts.get(member, 0)

        category = get_category(member)
        if category == "Other":
            continue

        if ocr_count > 0:
            final_count, confidence, method = ocr_count, 0.90, "OCR"
            ai_avg = (openai_count + gemini_count) / 2 if (openai_count + gemini_count) > 0 else 0
            if ai_avg > 0 and abs(ocr_count - ai_avg) / max(ocr_count, ai_avg) < 0.3:
                confidence, method = 0.95, "OCR+AI"
        elif openai_count > 0 or gemini_count > 0:
            if openai_count > 0 and gemini_count > 0:
                final_count, confidence, method = int(round(openai_count * 0.6 + gemini_count * 0.4)), 0.80, "AI"
            elif openai_count > 0:
                final_count, confidence, method = openai_count, 0.75, "OpenAI"
            else:
                final_count, confidence, method = gemini_count, 0.70, "Gemini"
        else:
            continue

        weight = get_weight(member)
        length = {"HSS": 15.0, "Joist": 30.0, "Beam": 25.0}.get(category, 20.0)

        results.append({
            "designation": member, "category": category, "quantity": final_count,
            "weight_per_ft": weight, "length_ft": length,
            "total_length": final_count * length, "total_weight": final_count * length * weight,
            "confidence": confidence, "method": method,
            "ocr_count": ocr_count, "openai_count": openai_count, "gemini_count": gemini_count,
            "positions": ocr_data["positions"].get(member, []),
        })
        
        if i % 10 == 0:
            print(f"  Processed {i}/{len(all_members)} members...")

    results.sort(key=lambda x: x["total_weight"], reverse=True)
    
    print(f"\n✅ Reconciliation Complete:")
    print(f"   Final Members: {sum(r['quantity'] for r in results)}")
    print(f"   Unique Types: {len(results)}")
    print(f"   Total Weight: {sum(r['total_weight'] for r in results):,.0f} lbs")
    print("="*80)
    
    return results


def create_highlighted_pdf(pdf_path, results, output_path, text_items=None):
    """Create Highlighted PDF with dimensions in YELLOW"""
    print("\n📄 Creating highlighted PDF...")
    doc = fitz.open(pdf_path)
    colors = {"Beam": (0, 0.7, 0), "HSS": (0.9, 0.5, 0), "Channel": (0.8, 0, 0.8),
              "Angle": (0, 0.8, 0.8), "Joist": (0.8, 0.8, 0)}
    
    # Highlight steel members (GREEN, ORANGE, etc.)
    member_count = 0
    for r in results:
        for pos in r["positions"]:
            if pos["page"] < len(doc):
                page = doc[pos["page"]]
                try:
                    rect = fitz.Rect(pos["bbox"]) + (-2, -2, 2, 2)
                    color = colors.get(r["category"], (0.5, 0.5, 0.5))
                    page.draw_rect(rect, color=color, fill=color, width=1, fill_opacity=0.3)
                    member_count += 1
                except:
                    pass
    
    # Highlight dimensions in YELLOW
    dimension_count = 0
    if text_items:
        dimensions = find_dimensions(text_items)
        print(f"  Highlighting {len(dimensions)} dimensions in yellow...")
        
        for dim in dimensions:
            page_num = dim['page']
            if page_num < len(doc):
                page = doc[page_num]
                try:
                    # Create yellow highlight box around dimension text
                    x, y = dim['x'], dim['y']
                    # Make box wider to cover dimension text
                    rect = fitz.Rect(x - 30, y - 8, x + 30, y + 8)
                    
                    # Draw yellow filled rectangle
                    page.draw_rect(rect,
                                  color=(1, 1, 0),      # Yellow border
                                  fill=(1, 1, 0),       # Yellow fill
                                  width=1,
                                  fill_opacity=0.4)     # Semi-transparent
                    dimension_count += 1
                except Exception as e:
                    pass
    
    # Add legend
    if len(doc) > 0:
        page = doc[0]
        legend_text = f"""MATERIAL TAKEOFF VISUALIZATION
{'='*40}
• BEAMS: Green
• HSS: Orange  
• CHANNELS: Magenta
• ANGLES: Cyan
• JOISTS: Yellow-Green
• DIMENSIONS: Yellow ←

Members Highlighted: {member_count}
Dimensions Highlighted: {dimension_count}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        rect = fitz.Rect(10, 10, 280, 160)
        page.draw_rect(rect, color=(0, 0, 0), fill=(1, 1, 0.9), width=2)
        page.insert_textbox(rect, legend_text, fontsize=8, fontname="helv", color=(0, 0, 0))
    
    doc.save(output_path)
    doc.close()
    print(f"✅ Saved: {os.path.basename(output_path)}")
    print(f"   Members highlighted: {member_count}")
    print(f"   Dimensions highlighted: {dimension_count}")


def create_excel(results, output_path, pdf_path):
    """Create Excel report"""
    print("📊 Creating Excel report...")
    
    rows = [{
        "Designation": r["designation"], "Category": r["category"], "Quantity": r["quantity"],
        "Weight (lbs/ft)": r["weight_per_ft"], "Length (ft)": r["length_ft"],
        "Total Length (ft)": r["total_length"], "Total Weight (lbs)": r["total_weight"],
        "Confidence": f"{r['confidence']*100:.0f}%", "Method": r["method"],
        "OCR": r["ocr_count"], "OpenAI": r["openai_count"], "Gemini": r["gemini_count"],
    } for r in results]

    df = pd.DataFrame(rows)
    summary = pd.DataFrame({
        "Metric": ["File", "Total Members", "Types", "Weight (lbs)", "Weight (tons)", "Date"],
        "Value": [os.path.basename(pdf_path), df["Quantity"].sum(), len(df),
                  f"{df['Total Weight (lbs)'].sum():,.0f}",
                  f"{df['Total Weight (lbs)'].sum()/2000:.2f}",
                  datetime.now().strftime("%Y-%m-%d %H:%M")],
    })

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Takeoff", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
    
    print(f"✅ Saved: {os.path.basename(output_path)}")


def find_dimensions(text_items):
    """Find dimensions - simplified"""
    dimensions = []
    for item in text_items:
        patterns = [r'(\d+)\s*[\'"]\s*[-–]\s*(\d+)\s*["\']', r'(\d+)\s*[\'"]']
        for pattern in patterns:
            match = re.search(pattern, item['text'])
            if match:
                try:
                    value_ft = float(match.group(1))
                    if 1 <= value_ft <= 200:
                        dimensions.append({'text': item['text'], 'value_ft': value_ft,
                                         'x': item['x'], 'y': item['y'], 'page': item['page']})
                        break
                except:
                    continue
    return dimensions