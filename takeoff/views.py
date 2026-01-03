"""
Views for Material Takeoff App - DIAGNOSTIC VERSION
This version includes detailed diagnostics to find where quality is lost
"""

import os
import time
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from collections import Counter

# Import your EXACT AI code (unchanged)
from .core import (
    extract_ocr,
    analyze_openai,
    analyze_gemini,
    reconcile,
    create_highlighted_pdf,
    create_excel,
)

from django.http import HttpResponse


def index(request):
    """Main page"""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Material Takeoff AI - Diagnostic Mode</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 700px;
            width: 100%;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 32px;
            text-align: center;
        }

        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .diagnostic-badge {
            background: #ff6b6b;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 20px;
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: #f8f9ff;
        }

        .upload-area:hover {
            background: #f0f2ff;
            border-color: #764ba2;
        }

        .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }

        input[type="file"] {
            display: none;
        }

        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: transform 0.2s;
        }

        .btn:hover {
            transform: translateY(-2px);
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .progress {
            display: none;
            margin-top: 20px;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }

        .progress-text {
            text-align: center;
            margin-top: 10px;
            color: #666;
            font-size: 14px;
        }

        .diagnostics {
            display: none;
            margin-top: 20px;
            padding: 20px;
            background: #fff3cd;
            border-radius: 10px;
            border: 2px solid #ffc107;
        }

        .diagnostics h4 {
            color: #856404;
            margin-bottom: 10px;
        }

        .diagnostic-item {
            padding: 5px 0;
            font-size: 14px;
            font-family: monospace;
            color: #666;
        }

        .diagnostic-item.good {
            color: #28a745;
        }

        .diagnostic-item.warning {
            color: #ffc107;
        }

        .diagnostic-item.bad {
            color: #dc3545;
        }

        .results {
            display: none;
            margin-top: 30px;
            padding: 20px;
            background: #f8f9ff;
            border-radius: 10px;
        }

        .result-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }

        .result-item:last-child {
            border-bottom: none;
        }

        .download-btn {
            background: #10b981;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            display: inline-block;
            margin: 10px 5px;
            transition: transform 0.2s;
        }

        .download-btn:hover {
            transform: translateY(-2px);
        }

        .error {
            display: none;
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            text-align: center;
        }

        .file-info {
            margin-top: 15px;
            padding: 10px;
            background: white;
            border-radius: 8px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align: center;">
            <span class="diagnostic-badge">🔬 DIAGNOSTIC MODE</span>
        </div>
        <h1>🏗️ Material Takeoff AI</h1>
        <p class="subtitle">Diagnostic mode enabled - detailed quality analysis</p>

        <form id="uploadForm">
            <div class="upload-area" onclick="document.getElementById('pdfInput').click()">
                <div class="upload-icon">📄</div>
                <h3>Click to Upload PDF</h3>
                <p>Structural drawings only</p>
                <input type="file" id="pdfInput" accept=".pdf" required>
            </div>

            <div class="file-info" id="fileInfo">
                <strong>Selected:</strong> <span id="fileName"></span>
            </div>

            <button type="submit" class="btn" id="processBtn">
                🚀 Process with AI (Diagnostic Mode)
            </button>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>AI is analyzing your drawing...<br>This may take 1-3 minutes</p>
        </div>

        <div class="progress" id="progress">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText">Starting...</div>
        </div>

        <div class="diagnostics" id="diagnostics">
            <h4>🔬 Quality Diagnostics</h4>
            <div id="diagnosticData"></div>
        </div>

        <div class="error" id="error"></div>

        <div class="results" id="results">
            <h3 style="margin-bottom: 15px;">✅ Analysis Complete!</h3>
            <div class="result-item">
                <span><strong>Total Members:</strong></span>
                <span id="totalMembers">-</span>
            </div>
            <div class="result-item">
                <span><strong>Member Types:</strong></span>
                <span id="totalTypes">-</span>
            </div>
            <div class="result-item">
                <span><strong>Total Weight:</strong></span>
                <span id="totalWeight">-</span>
            </div>
            <div class="result-item">
                <span><strong>Processing Time:</strong></span>
                <span id="procTime">-</span>
            </div>
            <div class="result-item">
                <span><strong>OCR Count:</strong></span>
                <span id="ocrCount">-</span>
            </div>
            <div class="result-item">
                <span><strong>AI Count:</strong></span>
                <span id="aiCount">-</span>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <h4>📥 Download Files:</h4>
                <a href="#" class="download-btn" id="downloadExcel">📊 Excel Takeoff</a>
                <a href="#" class="download-btn" id="downloadPdf">📄 Highlighted PDF</a>
            </div>
        </div>
    </div>

    <script>
        const pdfInput = document.getElementById('pdfInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const uploadForm = document.getElementById('uploadForm');
        const loading = document.getElementById('loading');
        const progress = document.getElementById('progress');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const diagnostics = document.getElementById('diagnostics');
        const diagnosticData = document.getElementById('diagnosticData');
        const results = document.getElementById('results');
        const error = document.getElementById('error');
        const processBtn = document.getElementById('processBtn');

        pdfInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                fileName.textContent = this.files[0].name;
                fileInfo.style.display = 'block';
            }
        });

        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            if (!pdfInput.files.length) {
                showError('Please select a PDF file');
                return;
            }

            const formData = new FormData();
            formData.append('pdf_file', pdfInput.files[0]);

            // Show loading
            loading.style.display = 'block';
            progress.style.display = 'block';
            results.style.display = 'none';
            error.style.display = 'none';
            diagnostics.style.display = 'none';
            processBtn.disabled = true;

            // Simulate progress
            let progressValue = 0;
            const progressInterval = setInterval(() => {
                progressValue += Math.random() * 15;
                if (progressValue > 90) progressValue = 90;
                progressFill.style.width = progressValue + '%';

                if (progressValue < 30) {
                    progressText.textContent = 'Reading PDF...';
                } else if (progressValue < 60) {
                    progressText.textContent = 'Running AI analysis...';
                } else {
                    progressText.textContent = 'Generating outputs...';
                }
            }, 500);

            try {
                const response = await fetch('/process/', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(progressInterval);
                progressFill.style.width = '100%';
                progressText.textContent = 'Complete!';

                const data = await response.json();

                if (data.success) {
                    // Show diagnostics
                    if (data.diagnostics) {
                        let diagHTML = '';
                        for (const [key, value] of Object.entries(data.diagnostics)) {
                            let className = 'good';
                            if (key.includes('warning')) className = 'warning';
                            if (key.includes('error') || key.includes('poor')) className = 'bad';

                            diagHTML += `<div class="diagnostic-item ${className}">▪ ${key}: ${value}</div>`;
                        }
                        diagnosticData.innerHTML = diagHTML;
                        diagnostics.style.display = 'block';
                    }

                    // Show results
                    document.getElementById('totalMembers').textContent = data.summary.total_members;
                    document.getElementById('totalTypes').textContent = data.summary.total_types;
                    document.getElementById('totalWeight').textContent =
                        `${data.summary.total_weight_lbs.toLocaleString()} lbs (${data.summary.total_weight_tons} tons)`;
                    document.getElementById('procTime').textContent = data.summary.processing_time;
                    document.getElementById('ocrCount').textContent = data.summary.ocr_found || 'N/A';
                    document.getElementById('aiCount').textContent = data.summary.ai_found || 'N/A';

                    document.getElementById('downloadExcel').href =
                        `/download/excel/${data.files.excel}/`;
                    document.getElementById('downloadPdf').href =
                        `/download/pdf/${data.files.pdf}/`;

                    results.style.display = 'block';
                } else {
                    showError(data.error || 'Processing failed');
                }
            } catch (err) {
                clearInterval(progressInterval);
                showError('Network error: ' + err.message);
            } finally {
                loading.style.display = 'none';
                progress.style.display = 'none';
                processBtn.disabled = false;
            }
        });

        function showError(message) {
            error.textContent = message;
            error.style.display = 'block';
        }
    </script>
</body>
</html>"""
    return HttpResponse(html)


@csrf_exempt
def process_pdf(request):
    """
    Process uploaded PDF using AI - DIAGNOSTIC VERSION
    This version adds detailed diagnostics to find where quality is lost
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    if "pdf_file" not in request.FILES:
        return JsonResponse({"error": "No PDF file uploaded"}, status=400)

    pdf_file = request.FILES["pdf_file"]

    # Validate file
    if not pdf_file.name.endswith(".pdf"):
        return JsonResponse({"error": "Only PDF files allowed"}, status=400)

    # Check file size
    if pdf_file.size > 50 * 1024 * 1024:  # 50MB limit
        return JsonResponse({"error": "File too large (max 50MB)"}, status=400)

    start_time = time.time()
    diagnostics = {}

    try:
        # Create media directory
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Save uploaded file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(
            c for c in pdf_file.name if c.isalnum() or c in ("_", "-", ".")
        )
        filename = f"{timestamp}_{clean_name}"
        pdf_path = os.path.join(settings.MEDIA_ROOT, filename)

        print(f"\n{'='*70}")
        print(f"🔬 DIAGNOSTIC MODE: {filename}")
        print(f"{'='*70}")

        # Write file with diagnostics
        bytes_written = 0
        with open(pdf_path, "wb") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
                bytes_written += len(chunk)

        # DIAGNOSTIC 1: File integrity
        actual_size = os.path.getsize(pdf_path)
        diagnostics["file_uploaded_size"] = f"{pdf_file.size:,} bytes"
        diagnostics["file_written_size"] = f"{actual_size:,} bytes"

        if actual_size != pdf_file.size:
            diagnostics["⚠️ file_size_mismatch"] = (
                f"Expected {pdf_file.size}, got {actual_size}"
            )
        else:
            diagnostics["✅ file_integrity"] = "Perfect match"

        # Verify file exists and is not empty
        if not os.path.exists(pdf_path) or actual_size == 0:
            return JsonResponse(
                {"error": "File upload failed - file is empty"}, status=500
            )

        # DIAGNOSTIC 2: PDF quality check
        import fitz
        from PIL import Image
        from io import BytesIO

        doc = fitz.open(pdf_path)
        diagnostics["pdf_pages"] = len(doc)

        if len(doc) > 0:
            page = doc[0]

            # Check PDF page dimensions
            rect = page.rect
            diagnostics["pdf_page_size"] = f"{rect.width:.0f}x{rect.height:.0f}"

            # Test image rendering at 200 DPI (your current DPI)
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            diagnostics["rendered_image_bytes"] = f"{len(img_bytes):,} bytes"

            # Check PIL conversion
            img = Image.open(BytesIO(img_bytes))
            diagnostics["image_size"] = f"{img.size[0]}x{img.size[1]}"
            diagnostics["image_mode"] = img.mode
            diagnostics["image_format"] = (
                img.format if img.format else "None (from bytes)"
            )

            # Quality assessment
            total_pixels = img.size[0] * img.size[1]
            diagnostics["total_pixels"] = f"{total_pixels:,}"

            if total_pixels < 500000:  # Less than 0.5 megapixels
                diagnostics["⚠️ image_quality"] = "LOW - May affect AI accuracy"
            elif total_pixels < 2000000:  # Less than 2 megapixels
                diagnostics["image_quality"] = "MEDIUM - Acceptable"
            else:
                diagnostics["✅ image_quality"] = "HIGH - Good for AI"

            # Check base64 size (what gets sent to AI)
            import base64

            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            diagnostics["base64_size"] = f"{len(img_b64):,} chars"

            if len(img_b64) < 10000:
                diagnostics["⚠️ base64_warning"] = "Image may be too compressed"

        doc.close()

        print("\n🔬 DIAGNOSTICS:")
        for key, value in diagnostics.items():
            print(f"   {key}: {value}")

        # Generate output filenames
        base_name = os.path.splitext(filename)[0]
        excel_filename = f"{base_name}_TAKEOFF.xlsx"
        highlighted_filename = f"{base_name}_HIGHLIGHTED.pdf"

        excel_path = os.path.join(settings.MEDIA_ROOT, excel_filename)
        highlighted_path = os.path.join(settings.MEDIA_ROOT, highlighted_filename)

        # Get API keys
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")

        diagnostics["openai_key_present"] = "Yes" if openai_key else "No"
        diagnostics["gemini_key_present"] = "Yes" if gemini_key else "No"

        if not openai_key and not gemini_key:
            diagnostics["⚠️ ai_warning"] = "No API keys - OCR only"

        # =================================================================
        # YOUR EXACT AI CODE RUNS HERE
        # =================================================================

        print("\n📋 Step 1/4: OCR Extraction...")
        ocr_data = extract_ocr(pdf_path)
        ocr_total = sum(sum(c.values()) for c in ocr_data["counts"].values())
        print(f"   ✅ Found {ocr_total} members via OCR")
        diagnostics["ocr_members_found"] = ocr_total

        print("\n🤖 Step 2/4: OpenAI Analysis...")
        if openai_key:
            openai_counts = analyze_openai(pdf_path, openai_key)
            print(f"   ✅ OpenAI found {len(openai_counts)} types")
            diagnostics["openai_types_found"] = len(openai_counts)
            diagnostics["openai_total_count"] = sum(openai_counts.values())
        else:
            openai_counts = Counter()
            print("   ⏭️ Skipped (no API key)")
            diagnostics["openai_status"] = "Skipped (no key)"

        print("\n🔮 Step 3/4: Gemini Analysis...")
        if gemini_key:
            gemini_counts = analyze_gemini(pdf_path, gemini_key)
            print(f"   ✅ Gemini found {len(gemini_counts)} types")
            diagnostics["gemini_types_found"] = len(gemini_counts)
            diagnostics["gemini_total_count"] = sum(gemini_counts.values())
        else:
            gemini_counts = Counter()
            print("   ⏭️ Skipped (no API key)")
            diagnostics["gemini_status"] = "Skipped (no key)"

        print("\n⚙️ Step 4/4: Generating Outputs...")
        results = reconcile(ocr_data, openai_counts, gemini_counts)

        # Verify results
        if not results:
            return JsonResponse(
                {
                    "error": "No structural members found in PDF",
                    "diagnostics": diagnostics,
                },
                status=400,
            )

        create_highlighted_pdf(pdf_path, results, highlighted_path)
        create_excel(results, excel_path, pdf_path)

        # Verify outputs
        if not os.path.exists(excel_path):
            return JsonResponse({"error": "Failed to generate Excel file"}, status=500)
        if not os.path.exists(highlighted_path):
            return JsonResponse({"error": "Failed to generate PDF file"}, status=500)

        # =================================================================
        # END AI CODE
        # =================================================================

        # Calculate summary
        total_members = sum(r["quantity"] for r in results)
        total_weight = sum(r["total_weight"] for r in results)
        processing_time = time.time() - start_time

        diagnostics["final_members"] = total_members
        diagnostics["final_types"] = len(results)
        diagnostics["processing_time"] = f"{processing_time:.1f}s"

        # Quality assessment
        if ocr_total > 0 and total_members == 0:
            diagnostics["⚠️ reconciliation_issue"] = (
                "OCR found items but final count is 0"
            )

        ai_total = sum(openai_counts.values()) + sum(gemini_counts.values())
        if ai_total > 0 and ai_total < ocr_total * 0.5:
            diagnostics["⚠️ ai_undercount"] = f"AI found {ai_total} vs OCR {ocr_total}"

        print(f"\n{'='*70}")
        print(f"✅ SUCCESS")
        print(f"{'='*70}")
        print(f"Members: {total_members}")
        print(f"Types: {len(results)}")
        print(f"Weight: {total_weight:,.0f} lbs")
        print(f"Time: {processing_time:.1f}s")
        print(f"{'='*70}\n")

        return JsonResponse(
            {
                "success": True,
                "summary": {
                    "total_members": total_members,
                    "total_types": len(results),
                    "total_weight_lbs": int(total_weight),
                    "total_weight_tons": round(total_weight / 2000, 2),
                    "processing_time": f"{processing_time:.1f}s",
                    "ocr_found": ocr_total,
                    "ai_found": ai_total,
                },
                "files": {"excel": excel_filename, "pdf": highlighted_filename},
                "diagnostics": diagnostics,
            }
        )

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"\n❌ ERROR:\n{error_details}\n")

        return JsonResponse(
            {
                "error": f"Processing failed: {str(e)}",
                "details": error_details if settings.DEBUG else None,
                "diagnostics": diagnostics,
            },
            status=500,
        )


def download_file(request, file_type, filename):
    """Download generated files"""
    filename = os.path.basename(filename)
    file_path = os.path.join(settings.MEDIA_ROOT, filename)

    if not os.path.exists(file_path):
        raise Http404("File not found")

    if not os.path.abspath(file_path).startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404("Invalid file path")

    return FileResponse(open(file_path, "rb"), as_attachment=True, filename=filename)
