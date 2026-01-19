"""
Material Takeoff Core - Simple Version (No AI APIs needed)
Based on your perfect structural take-off system
"""

import os
import re
import math
import pandas as pd
import fitz  # PyMuPDF
from collections import defaultdict, Counter
from datetime import datetime

# =============================================================================
# 1. PDF PROCESSOR
# =============================================================================

class PDFProcessor:
    """PDF processor with text extraction"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    def extract_text(self):
        """Extract text with layout"""
        print(f"\n📄 Processing PDF: {os.path.basename(self.pdf_path)}")

        all_elements = []

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]

            # Extract text blocks
            blocks = page.get_text("dict")["blocks"]
            page_elements = []

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        spans_data = []

                        for span in line["spans"]:
                            span_text = span["text"].strip()
                            if span_text:
                                line_text += span_text + " "
                                spans_data.append({
                                    'text': span_text,
                                    'bbox': span["bbox"],
                                    'size': span["size"],
                                    'font': span["font"]
                                })

                        if line_text.strip() and spans_data:
                            x0 = min(s['bbox'][0] for s in spans_data)
                            y0 = min(s['bbox'][1] for s in spans_data)
                            x1 = max(s['bbox'][2] for s in spans_data)
                            y1 = max(s['bbox'][3] for s in spans_data)

                            element = {
                                'text': line_text.strip(),
                                'bbox': (x0, y0, x1, y1),
                                'center_x': (x0 + x1) / 2,
                                'center_y': (y0 + y1) / 2,
                                'page': page_num,
                                'font_size': spans_data[0]['size'],
                                'type': 'text'
                            }

                            page_elements.append(element)
                            all_elements.append(element)

            print(f"  Page {page_num+1}: Extracted {len(page_elements)} text elements")

        print(f"✅ Total elements extracted: {len(all_elements)}")
        return all_elements

    def find_dimensions(self, elements):
        """Find dimensions in the drawing"""
        print("\n📐 Finding dimensions...")

        dimensions = []

        for elem in elements:
            text = elem['text'].strip()

            # Dimension patterns
            patterns = [
                r'(\d+)\s*[\'"]\s*[-–]\s*(\d+)\s*["\']',  # 26'-0"
                r'(\d+)\s*[\'"]$',  # 26'
                r'(\d+)\s*-\s*(\d+)\s*$',  # 26-0
                r'^(\d+(?:\.\d+)?)\s*FT$',  # 26.0 FT
            ]

            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        if len(match.groups()) == 2:
                            feet = float(match.group(1))
                            inches = float(match.group(2)) if match.group(2) else 0
                            length_ft = feet + (inches / 12.0)
                        else:
                            length_ft = float(match.group(1))

                        if 1 <= length_ft <= 200:
                            dimensions.append({
                                'text': text,
                                'length_ft': length_ft,
                                'x': elem['center_x'],
                                'y': elem['center_y'],
                                'page': elem['page'],
                                'bbox': elem['bbox']
                            })
                            break
                    except:
                        continue

        print(f"  Found {len(dimensions)} dimensions")

        # Group common dimensions
        dimension_groups = defaultdict(list)
        for dim in dimensions:
            key = round(dim['length_ft'], 1)
            dimension_groups[key].append(dim)

        # Find most common spans
        common_spans = []
        for length, dims in dimension_groups.items():
            if len(dims) >= 2:
                common_spans.append({
                    'length_ft': length,
                    'count': len(dims),
                    'example': dims[0]['text']
                })

        common_spans.sort(key=lambda x: x['count'], reverse=True)

        if common_spans:
            print(f"  Most common spans:")
            for span in common_spans[:5]:
                print(f"    {span['length_ft']} ft: {span['count']} times")

        return {
            'dimensions': dimensions,
            'common_spans': common_spans,
            'dimension_groups': dimension_groups
        }

    def close(self):
        self.doc.close()


# =============================================================================
# 2. STRUCTURAL MEMBER DETECTOR
# =============================================================================

SECTION_PATTERNS = [
    (r'(W\d+X\d+(?:\.\d+)?)', 'Beam'),
    (r'(HSS\d+X\d+X[\d/]+)', 'HSS'),
    (r'(HSS\d+\.\d+X\d+\.\d+X[\d\.]+)', 'HSS'),
    (r'(L\d+X\d+X[\d/]+)', 'Angle'),
    (r'(C\d+X[\d\.]+)', 'Channel'),
    (r'(MC\d+X[\d\.]+)', 'Channel'),
    (r'(PL\d+X\d+)', 'Plate'),
    (r'(WT\d+X\d+(?:\.\d+)?)', 'Tee'),
]


def find_members(elements):
    """Find all structural members"""
    print("\n🔍 Detecting structural members...")

    members = []
    found_designations = set()

    for elem in elements:
        text = elem['text'].upper()

        # Skip non-structural
        skip_keywords = ['EXISTING', 'EXIST', 'EX.', '(EX)', 'NOTE', 'NOTES',
                       'TYPICAL', 'TYP.', 'SEE', 'REFER', 'DETAIL', 'SCHEDULE']

        if any(keyword in text for keyword in skip_keywords):
            continue

        # Check patterns
        for pattern, mtype in SECTION_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                designation = match.group(1)

                # Avoid duplicates
                member_key = f"{designation}_{elem['page']}_{elem['center_x']:.0f}_{elem['center_y']:.0f}"
                if member_key in found_designations:
                    continue

                found_designations.add(member_key)

                # Extract quantity
                quantity = 1
                qty_match = re.search(r'\[(\d+)\]', text)
                if qty_match:
                    quantity = int(qty_match.group(1))

                qty_match = re.search(r'QTY\s*[\(\[]?\s*(\d+)\s*[\)\]]?', text, re.IGNORECASE)
                if qty_match:
                    quantity = int(qty_match.group(1))

                members.append({
                    'designation': designation,
                    'type': mtype,
                    'original_text': text,
                    'page': elem['page'],
                    'x': elem['center_x'],
                    'y': elem['center_y'],
                    'bbox': elem['bbox'],
                    'quantity': quantity,
                })

    print(f"✅ Found {len(members)} structural member instances")

    # Show breakdown
    type_count = Counter([m['type'] for m in members])
    for mtype, count in type_count.most_common():
        print(f"  {mtype}: {count}")

    return members


def assign_lengths(members, dim_data):
    """Assign lengths to members"""
    print("\n📏 Assigning lengths...")

    common_spans = dim_data.get('common_spans', [])
    dimensions = dim_data.get('dimensions', [])

    # Default lengths
    default_lengths = {
        'Beam': 26.0,
        'HSS': 14.0,
        'Angle': 10.0,
        'Channel': 20.0,
        'Plate': 5.0,
        'Tee': 15.0,
    }

    for member in members:
        mtype = member['type']

        # Find nearby dimensions
        page_dims = [d for d in dimensions if d['page'] == member['page']]

        if page_dims:
            closest = None
            min_dist = float('inf')

            for dim in page_dims:
                dist = math.sqrt((dim['x'] - member['x'])**2 + (dim['y'] - member['y'])**2)
                if dist < min_dist and dist < 100:
                    min_dist = dist
                    closest = dim

            if closest and min_dist < 50:
                member['length_ft'] = closest['length_ft']
                member['measurement'] = f"Near: {closest['text']}"
                continue

        # Use common span for beams
        if mtype == 'Beam' and common_spans:
            most_common = common_spans[0]['length_ft']
            member['length_ft'] = most_common
            member['measurement'] = f"Common span: {most_common} ft"
        else:
            default_len = default_lengths.get(mtype, 20.0)
            member['length_ft'] = default_len
            member['measurement'] = f"Typical {mtype.lower()} length"

    print("✅ Length assignment complete")
    return members


# =============================================================================
# 3. WEIGHT CALCULATOR
# =============================================================================

def calculate_weight(designation: str) -> float:
    """Calculate weight for section"""
    designation_upper = designation.upper()

    # W shape pattern
    w_match = re.match(r'W(\d+)X(\d+(?:\.\d+)?)', designation_upper)
    if w_match:
        try:
            weight = float(w_match.group(2))
            if 10 <= weight <= 1000:
                return weight
        except:
            pass

    # HSS pattern - approximate
    hss_match = re.match(r'HSS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X([\d\./]+)', designation_upper)
    if hss_match:
        try:
            width = float(hss_match.group(1))
            height = float(hss_match.group(2))
            thickness_str = hss_match.group(3)

            if '/' in thickness_str:
                num, denom = thickness_str.split('/')
                thickness = float(num) / float(denom)
            else:
                thickness = float(thickness_str)

            perimeter = 2 * (width + height)
            weight = perimeter * thickness * 3.4
            return max(weight, 5)
        except:
            pass

    # Default
    if designation_upper.startswith('W'):
        return 100.0
    elif designation_upper.startswith('HSS'):
        return 50.0
    elif designation_upper.startswith('L'):
        return 15.0
    elif designation_upper.startswith('C') or designation_upper.startswith('MC'):
        return 20.0
    else:
        return 30.0


# =============================================================================
# 4. EXCEL REPORT GENERATOR
# =============================================================================

def create_excel(members, pdf_path, output_path):
    """Create Excel report"""
    print("\n📊 Creating Excel report...")

    # Group members
    groups = defaultdict(lambda: {
        'type': '',
        'quantities': [],
        'lengths': [],
        'methods': set(),
        'weights': [],
    })

    for member in members:
        key = member['designation']
        groups[key]['type'] = member['type']
        groups[key]['quantities'].append(member['quantity'])
        groups[key]['lengths'].append(member.get('length_ft', 20.0))
        groups[key]['methods'].add(member.get('measurement', ''))
        groups[key]['weights'].append(calculate_weight(member['designation']))

    # Create report data
    report_data = []

    for designation, data in groups.items():
        total_qty = sum(data['quantities'])

        # Most common length
        if data['lengths']:
            length_counts = Counter([round(l, 1) for l in data['lengths']])
            most_common_length = length_counts.most_common(1)[0][0]
        else:
            most_common_length = 20.0

        # Average weight
        avg_weight = sum(data['weights']) / len(data['weights']) if data['weights'] else 0

        # Calculate totals
        total_length = most_common_length * total_qty
        total_weight = avg_weight * total_length if avg_weight > 0 else 0

        report_data.append({
            'Designation': designation,
            'Type': data['type'],
            'Length (ft)': round(most_common_length, 2),
            'Quantity': total_qty,
            'Total Length (ft)': round(total_length, 2),
            'Weight (lbs/ft)': round(avg_weight, 2),
            'Total Weight (lbs)': round(total_weight, 2),
            'Total Weight (tons)': round(total_weight/2000, 3),
        })

    # Sort by type and designation
    report_data.sort(key=lambda x: (x['Type'], x['Designation']))

    # Create DataFrame
    df = pd.DataFrame(report_data)

    # Summary
    total_members = sum(r['Quantity'] for r in report_data)
    total_weight_lbs = sum(r['Total Weight (lbs)'] for r in report_data)

    summary_data = {
        'Metric': ['File', 'Total Members', 'Unique Types', 'Total Weight (lbs)', 'Total Weight (tons)', 'Date'],
        'Value': [
            os.path.basename(pdf_path),
            total_members,
            len(report_data),
            f"{total_weight_lbs:,.0f}",
            f"{total_weight_lbs/2000:.2f}",
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    # Save Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Takeoff', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    print(f"✅ Excel saved: {os.path.basename(output_path)}")
    print(f"   Total members: {total_members}")
    print(f"   Total weight: {total_weight_lbs/2000:.1f} tons")


# =============================================================================
# 5. HIGHLIGHTED PDF GENERATOR
# =============================================================================

def create_highlighted_pdf(pdf_path, members, dim_data, output_path):
    """Create highlighted PDF"""
    print("\n🎨 Creating highlighted PDF...")

    doc = fitz.open(pdf_path)

    # Colors
    colors = {
        'Beam': (0, 0.8, 0),        # Green
        'HSS': (1, 0.5, 0),         # Orange
        'Angle': (0, 0, 1),         # Blue
        'Channel': (0.8, 0, 0.8),   # Magenta
        'Plate': (1, 0, 0),         # Red
        'Tee': (0, 0.8, 0.8),       # Cyan
    }

    # Highlight members
    member_count = 0
    for member in members:
        page_num = member['page']
        if page_num < len(doc):
            page = doc[page_num]
            try:
                x0, y0, x1, y1 = member['bbox']
                rect = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
                color = colors.get(member['type'], (0.5, 0.5, 0.5))

                page.draw_rect(rect, color=color, fill=color, width=1, fill_opacity=0.3)
                member_count += 1
            except:
                pass

    # Highlight dimensions in YELLOW
    dimension_count = 0
    for dim in dim_data.get('dimensions', []):
        page_num = dim['page']
        if page_num < len(doc):
            page = doc[page_num]
            try:
                x0, y0, x1, y1 = dim['bbox']
                rect = fitz.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
                page.draw_rect(rect, color=(1, 1, 0), fill=(1, 1, 0), width=1, fill_opacity=0.4)
                dimension_count += 1
            except:
                pass

    # Add legend
    if len(doc) > 0:
        page = doc[0]
        legend_text = f"""TAKEOFF VISUALIZATION
{'='*30}
• BEAMS: Green
• HSS: Orange
• ANGLES: Blue
• CHANNELS: Magenta
• DIMENSIONS: Yellow

Members: {member_count}
Dimensions: {dimension_count}

{datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        rect = fitz.Rect(10, 10, 200, 150)
        page.draw_rect(rect, color=(0, 0, 0), fill=(1, 1, 1), width=2)
        page.insert_textbox(rect, legend_text, fontsize=7, fontname="helv", color=(0, 0, 0))

    doc.save(output_path)
    doc.close()

    print(f"✅ PDF saved: {os.path.basename(output_path)}")
    print(f"   Members highlighted: {member_count}")
    print(f"   Dimensions highlighted: {dimension_count}")


# =============================================================================
# 6. MAIN PROCESSING FUNCTION
# =============================================================================

def process_takeoff(pdf_path, output_dir=None):
    """Main processing pipeline"""
    print("="*80)
    print("🏗️  STRUCTURAL TAKE-OFF PROCESSING")
    print("="*80)

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or "."

    try:
        # Step 1: Extract text
        processor = PDFProcessor(pdf_path)
        elements = processor.extract_text()

        # Step 2: Find dimensions
        dim_data = processor.find_dimensions(elements)

        # Step 3: Detect members
        members = find_members(elements)

        if not members:
            print("❌ No structural members found")
            processor.close()
            return None

        # Step 4: Assign lengths
        members = assign_lengths(members, dim_data)

        # Generate output filenames
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        excel_path = os.path.join(output_dir, f"{base_name}_TAKEOFF.xlsx")
        pdf_output_path = os.path.join(output_dir, f"{base_name}_HIGHLIGHTED.pdf")

        # Step 5: Create Excel
        create_excel(members, pdf_path, excel_path)

        # Step 6: Create highlighted PDF
        create_highlighted_pdf(pdf_path, members, dim_data, pdf_output_path)

        # Close
        processor.close()

        # Summary
        total_qty = sum(m['quantity'] for m in members)
        total_length = sum(m.get('length_ft', 0) * m['quantity'] for m in members)

        print("\n" + "="*80)
        print("✅ PROCESSING COMPLETE")
        print("="*80)
        print(f"Total Members: {total_qty}")
        print(f"Total Length: {total_length:,.1f} ft")
        print("="*80)

        return {
            'excel_path': excel_path,
            'pdf_path': pdf_output_path,
            'total_members': total_qty,
            'total_length': total_length,
            'members': members
        }

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None