"""
Material Takeoff Core - Integrated with StructuralTakeoffV12
Enhanced version with anti-ghost detection and proper line matching
"""

import os
import re
import math
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
from datetime import datetime

# =============================================================================
# MAIN STRUCTURAL TAKEOFF CLASS (V12 - Enhanced)
# =============================================================================

class StructuralTakeoffV12:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.final_data = []

    def get_distance(self, p1, p2):
        """Calculate Euclidean distance between two points"""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def is_line_orthogonal(self, p1, p2):
        """Returns True if line is roughly Horizontal or Vertical."""
        dy = abs(p1[1] - p2[1])
        dx = abs(p1[0] - p2[0])
        return dy < 2.0 or dx < 2.0

    def parse_dimension_text(self, text):
        """Parse dimension text to extract feet value"""
        match_ft_in = re.search(r"(\d+)'\s*-\s*(\d+)\"", text)
        if match_ft_in:
            return float(match_ft_in.group(1)) + float(match_ft_in.group(2))/12.0
        match_ft = re.search(r"(\d+)'", text)
        if match_ft:
            return float(match_ft.group(1))
        return None

    def calibrate_page_scale(self, page, text_blocks):
        """Calibrate the scale (pixels per foot) for the page"""
        candidates = []
        for b in text_blocks:
            val = self.parse_dimension_text(b['text'])
            if val and 4.0 <= val <= 100.0:
                candidates.append({'val': val, 'rect': b['rect']})

        grid_lines = []
        for path in page.get_drawings():
            for item in path["items"]:
                if item[0] == "l":
                    p1, p2 = item[1], item[2]
                    length = self.get_distance(p1, p2)
                    if length > 50:
                        grid_lines.append({'x': p1[0], 'y': p1[1]})

        scales = []
        for cand in candidates:
            rect = cand['rect']
            cx = (rect.x0 + rect.x1) / 2
            cy = (rect.y0 + rect.y1) / 2
            
            left = [l['x'] for l in grid_lines if l['x'] < cx and abs(l['y'] - cy) < 60]
            right = [l['x'] for l in grid_lines if l['x'] > cx and abs(l['y'] - cy) < 60]
            
            if left and right:
                px_dist = min(right) - max(left)
                ppf = px_dist / cand['val']
                if 0.5 < ppf < 100.0:
                    scales.append(ppf)

        if scales:
            return float(np.median(scales))
        return None

    def round_to_nearest_half(self, num):
        """Round to nearest 0.5 feet"""
        return round(num * 2) / 2

    def extract_base_profile(self, text):
        """Extracts just 'W24x55' from 'W24x55 [24] C=1'"""
        match = re.search(r'(W\d+x\d+(\.\d+)?)|(HSS\d+x\d+x[\d/]+)|(C\d+x[\d\.]+)|(L\d+x\d+x[\d/]+)|(\d+[K|LH]\d*)', text, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return text

    def extract_materials(self):
        """Extract all structural materials from PDF with anti-ghost detection"""
        print("\n🔍 Extracting structural materials...")
        
        patterns = [
            (r'W\d+x\d+', 'Beam (W)'),
            (r'HSS\d+x\d+x[\d/]+', 'HSS Tube'),
            (r'[MC]\d+x[\d\.]+', 'Channel'),
            (r'L\d+x\d+x[\d/]+', 'Angle'),
            (r'\d+[K|LH]\d*', 'Joist'),
            (r'BP\d+', 'Base Plate'),
        ]
        
        existing_keywords = [r'\(E\)', r'\(EX\)', r'EXIST', r'REMOVE']
        vertical_keywords = ['POST', 'COL', 'COLUMN', 'BP', 'PLATE', 'PC', 'TYP', 'VIF', 'RAIL']

        for page_num, page in enumerate(self.doc):
            print(f"  📄 Processing Page {page_num + 1}...")
            page_width = page.rect.width

            # --- A. Text Extraction with STRICT SPATIAL CLUSTERING (Anti-Ghost) ---
            text_blocks = []
            
            # 1. Get ALL raw text first
            raw_items = []
            for b in page.get_text("dict")["blocks"]:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            txt = s['text'].strip()
                            if not txt: continue
                            if any(re.search(k, txt, re.IGNORECASE) for k in existing_keywords):
                                continue
                            
                            bbox = s['bbox']
                            cx = (bbox[0] + bbox[2]) / 2
                            cy = (bbox[1] + bbox[3]) / 2
                            raw_items.append({'text': txt, 'rect': fitz.Rect(bbox), 'center': (cx, cy)})

            # 2. Filter Duplicates (The "Ghost Destroyer")
            # If we accept a label, we ban any identical label within 30 pixels
            accepted_items = []
            
            for item in raw_items:
                is_duplicate = False
                for accepted in accepted_items:
                    # Check text match
                    if item['text'] == accepted['text']:
                        # Check distance (if within 30px, it's the same label)
                        dist = math.sqrt((item['center'][0] - accepted['center'][0])**2 + (item['center'][1] - accepted['center'][1])**2)
                        if dist < 30:
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    accepted_items.append(item)

            # --- B. Calibration ---
            ppf = self.calibrate_page_scale(page, accepted_items)
            current_ppf = ppf if ppf else 4.0
            print(f"    Scale: {current_ppf:.2f} px/ft")

            # --- C. Line Detection (With Usage Flags) ---
            drawings = page.get_drawings()
            widths = [p.get("width", 1.0) for p in drawings if p.get("width") is not None and p.get("width") > 0.1]
            
            bold_thresh = 1.0
            if widths:
                widths.sort()
                bold_thresh = widths[int(len(widths) * 0.85)]

            vectors = []
            for path in drawings:
                w = path.get("width")
                if w is None: w = 1.0
                
                if w >= bold_thresh * 0.9:
                    for item in path["items"]:
                        if item[0] == "l":
                            p1, p2 = item[1], item[2]
                            length = self.get_distance(p1, p2)
                            # GRID FILTER: Ignore lines > 30% of page width
                            if length > (page_width * 0.3): continue
                            
                            if length > 15 and self.is_line_orthogonal(p1, p2):
                                # 'used': False is the key to preventing double counting
                                vectors.append({
                                    'len': length,
                                    'mid': ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2),
                                    'p1': p1, 'p2': p2,
                                    'used': False
                                })

            # --- D. Matching (THE "ONE-TICKET" SYSTEM) ---
            for block in accepted_items:
                txt = block['text']
                
                mtype = None
                for pat, name in patterns:
                    if re.search(pat, txt, re.IGNORECASE):
                        mtype = name
                        break
                
                if mtype:
                    # Clean the name to get quantity
                    qty = 1
                    qty_match = re.search(r'^(\d+)\s|[\(\[](\d+)[\)\]]', txt)
                    if qty_match:
                        qty = int(qty_match.group(1) or qty_match.group(2))
                    
                    # Clean for Designation (remove leading quantity)
                    designation = re.sub(r'^(\d+)\s|[\(\[](\d+)[\)\]]', '', txt).strip()

                    # Extract Base Profile for sorting/grouping
                    base_profile = self.extract_base_profile(designation)

                    is_vertical = any(k in txt.upper() for k in vertical_keywords)
                    matched_geom = None
                    
                    if is_vertical:
                        final_len = 0
                        method = "Count Only"
                    else:
                        best_match = None
                        min_dist = float('inf')
                        
                        # Find best match that is NOT USED
                        for v in vectors:
                            if v['used']: continue # Skip lines already claimed by another label
                            
                            dist = self.get_distance(block['center'], v['mid'])
                            if dist < min_dist:
                                min_dist = dist
                                best_match = v

                        if best_match and min_dist < 50:
                            # CRITICAL: Mark this line as USED. No other label can count it now.
                            best_match['used'] = True
                            
                            feet = best_match['len'] / current_ppf
                            if feet > 1.5:
                                final_len = self.round_to_nearest_half(feet)
                                method = "Measured"
                                matched_geom = {'p1': best_match['p1'], 'p2': best_match['p2']}
                            else:
                                final_len = 0
                                method = "Artifact"
                        else:
                            # If no UNUSED line is found nearby, assume this label is an orphan/duplicate and count as 0 length
                            final_len = 0
                            method = "Count Only (No Free Line)"

                    self.final_data.append({
                        'Page': page_num,
                        'Designation': designation,
                        'Base_Profile': base_profile, # W24x55
                        'Type': mtype,
                        'Quantity': qty,
                        'Length_Ft': final_len,
                        'Total_Length_Ft': final_len * qty,
                        'Method': method,
                        'Text_Rect': block['rect'],
                        'Line_Geom': matched_geom
                    })

        print(f"✅ Found {len(self.final_data)} structural member instances")

    def generate_outputs(self, output_dir=None):
        """Generate Excel and PDF outputs"""
        print("\n📊 Generating outputs...")
        
        if output_dir is None:
            output_dir = os.path.dirname(self.pdf_path) or "."
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        excel_name = os.path.join(output_dir, f"{base_name}_Consolidated_V12_{timestamp}.xlsx")
        pdf_name = os.path.join(output_dir, f"{base_name}_Visual_V12_{timestamp}.pdf")

        df = pd.DataFrame(self.final_data)
        if df.empty:
            print("❌ No structural members found.")
            return None

        # Filter out artifacts
        df_clean = df[df['Method'] != "Artifact"]

        # --- CONSOLIDATION STEP (Strict) ---
        # We group by Base_Profile (e.g. W24x55) AND Designation (W24x55 [24]) AND Length
        # This ensures exact matches are merged.
        
        bill_of_materials = df_clean.groupby(['Type', 'Base_Profile', 'Designation', 'Length_Ft', 'Method']).agg({
            'Quantity': 'sum',
            'Total_Length_Ft': 'sum'
        }).reset_index()

        # Sort nicely
        bill_of_materials.sort_values(by=['Type', 'Base_Profile', 'Length_Ft'], inplace=True)

        # --- SUMMARY STEP (Loose) ---
        # Just sums by Profile, regardless of length or studs
        profile_summary = df_clean.groupby(['Type', 'Base_Profile']).agg({
            'Quantity': 'sum',
            'Total_Length_Ft': 'sum'
        }).reset_index()

        # Save Excel
        with pd.ExcelWriter(excel_name, engine='openpyxl') as writer:
            bill_of_materials.to_excel(writer, sheet_name='Bill of Materials', index=False)
            profile_summary.to_excel(writer, sheet_name='Profile Summary', index=False)
        
        print(f"✅ Excel saved: {os.path.basename(excel_name)}")
        print("   → 'Bill of Materials' tab: Fully consolidated list")
        print("   → 'Profile Summary' tab: Total footage per beam size")

        # PDF Generation with highlighting
        print("🎨 Generating visual check PDF...")
        col_box = (0, 0, 1)  # Blue for text boxes
        col_line = (1, 0, 0)  # Red for lines
        
        for item in self.final_data:
            page = self.doc[item['Page']]
            if 'Text_Rect' in item:
                page.draw_rect(item['Text_Rect'], color=col_box, width=1.0)
            if item['Line_Geom']:
                p1 = item['Line_Geom']['p1']
                p2 = item['Line_Geom']['p2']
                page.draw_line(p1, p2, color=col_line, width=2.5)
                lp = fitz.Point(p1[0], p1[1]-5)
                page.insert_text(lp, f"L={item['Length_Ft']}'", color=col_line, fontsize=8)

        self.doc.save(pdf_name)
        print(f"✅ PDF saved: {os.path.basename(pdf_name)}")

        # Calculate totals
        total_members = int(df_clean['Quantity'].sum())
        total_length = float(df_clean['Total_Length_Ft'].sum())

        return {
            'excel_path': excel_name,
            'pdf_path': pdf_name,
            'total_members': total_members,
            'total_length': total_length,
            'members': self.final_data
        }

    def close(self):
        """Close the PDF document"""
        self.doc.close()


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================

def process_takeoff(pdf_path, output_dir=None):
    """
    Main processing pipeline that integrates with Django frontend
    
    Args:
        pdf_path: Path to the input PDF file
        output_dir: Directory for output files (optional)
    
    Returns:
        Dictionary with processing results or None on failure
    """
    print("="*80)
    print("🏗️  STRUCTURAL TAKE-OFF PROCESSING (V12 Enhanced)")
    print("="*80)

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or "."

    try:
        # Create the takeoff processor
        processor = StructuralTakeoffV12(pdf_path)
        
        # Extract materials
        processor.extract_materials()
        
        # Check if we found anything
        if not processor.final_data:
            print("❌ No structural members found")
            processor.close()
            return None
        
        # Generate outputs
        results = processor.generate_outputs(output_dir)
        
        # Close the document
        processor.close()
        
        if results:
            print("\n" + "="*80)
            print("✅ PROCESSING COMPLETE")
            print("="*80)
            print(f"Total Members: {results['total_members']}")
            print(f"Total Length: {results['total_length']:,.1f} ft")
            print("="*80)
        
        return results

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None