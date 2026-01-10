"""
Views with Enhanced Console Logging - FIXED DIMENSION HIGHLIGHTING
"""

import os
import sys
import time
from io import StringIO
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from collections import Counter

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
    """Main page - unchanged"""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Material Takeoff AI</title>
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

        .console-logs {
            display: none;
            margin-top: 20px;
            padding: 15px;
            background: #1e1e1e;
            color: #0f0;
            border-radius: 10px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }

        .console-logs h4 {
            color: #fff;
            margin-bottom: 10px;
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
        <h1>🏗️ Material Takeoff AI</h1>
        <p class="subtitle">Upload PDF → AI Analysis → Excel + Highlighted PDF</p>

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
                🚀 Process with AI
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

        <div class="console-logs" id="consoleLogs">
            <h4>📋 Console Output:</h4>
            <pre id="consoleContent"></pre>
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
        const consoleLogs = document.getElementById('consoleLogs');
        const consoleContent = document.getElementById('consoleContent');
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

            loading.style.display = 'block';
            progress.style.display = 'block';
            results.style.display = 'none';
            error.style.display = 'none';
            consoleLogs.style.display = 'none';
            processBtn.disabled = true;

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
                    // Show console logs
                    if (data.console_output) {
                        consoleContent.textContent = data.console_output;
                        consoleLogs.style.display = 'block';
                    }

                    // Show results
                    document.getElementById('totalMembers').textContent = data.summary.total_members;
                    document.getElementById('totalTypes').textContent = data.summary.total_types;
                    document.getElementById('totalWeight').textContent =
                        `${data.summary.total_weight_lbs.toLocaleString()} lbs (${data.summary.total_weight_tons} tons)`;
                    document.getElementById('procTime').textContent = data.summary.processing_time;

                    document.getElementById('downloadExcel').href =
                        `/download/excel/${data.files.excel}/`;
                    document.getElementById('downloadPdf').href =
                        `/download/pdf/${data.files.pdf}/`;

                    results.style.display = 'block';
                } else {
                    showError(data.error || 'Processing failed');
                    if (data.console_output) {
                        consoleContent.textContent = data.console_output;
                        consoleLogs.style.display = 'block';
                    }
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
    Process uploaded PDF - with FIXED dimension highlighting
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    if "pdf_file" not in request.FILES:
        return JsonResponse({"error": "No PDF file uploaded"}, status=400)

    pdf_file = request.FILES["pdf_file"]

    if not pdf_file.name.endswith(".pdf"):
        return JsonResponse({"error": "Only PDF files allowed"}, status=400)

    if pdf_file.size > 50 * 1024 * 1024:
        return JsonResponse({"error": "File too large (max 50MB)"}, status=400)

    # Capture console output
    console_capture = StringIO()
    old_stdout = sys.stdout
    sys.stdout = console_capture

    start_time = time.time()

    try:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(
            c for c in pdf_file.name if c.isalnum() or c in ("_", "-", ".")
        )
        filename = f"{timestamp}_{clean_name}"
        pdf_path = os.path.join(settings.MEDIA_ROOT, filename)

        print(f"\n{'='*70}")
        print(f"🏗️  PROCESSING: {filename}")
        print(f"{'='*70}")

        # Save file
        with open(pdf_path, "wb") as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)

        actual_size = os.path.getsize(pdf_path)

        if not os.path.exists(pdf_path) or actual_size == 0:
            sys.stdout = old_stdout
            return JsonResponse({"error": "File upload failed"}, status=500)

        # Generate filenames
        base_name = os.path.splitext(filename)[0]
        excel_filename = f"{base_name}_TAKEOFF.xlsx"
        highlighted_filename = f"{base_name}_HIGHLIGHTED.pdf"

        excel_path = os.path.join(settings.MEDIA_ROOT, excel_filename)
        highlighted_path = os.path.join(settings.MEDIA_ROOT, highlighted_filename)

        # Get API keys
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")

        # Run AI processing
        print("\n📋 Step 1/4: OCR Extraction...")
        ocr_data = extract_ocr(pdf_path)
        ocr_total = sum(sum(c.values()) for c in ocr_data["counts"].values())

        print("\n🤖 Step 2/4: OpenAI Analysis...")
        openai_counts = analyze_openai(pdf_path, openai_key) if openai_key else Counter()

        print("\n🔮 Step 3/4: Gemini Analysis...")
        gemini_counts = analyze_gemini(pdf_path, gemini_key) if gemini_key else Counter()

        print("\n⚙️ Step 4/4: Generating Outputs...")
        results = reconcile(ocr_data, openai_counts, gemini_counts)

        if not results:
            sys.stdout = old_stdout
            console_output = console_capture.getvalue()
            return JsonResponse(
                {
                    "error": "No structural members found",
                    "console_output": console_output,
                },
                status=400,
            )

        # CREATE HIGHLIGHTED PDF - PASS text_items for dimension highlighting
        create_highlighted_pdf(pdf_path, results, highlighted_path, text_items=ocr_data.get("text_items"))
        
        create_excel(results, excel_path, pdf_path)

        if not os.path.exists(excel_path):
            sys.stdout = old_stdout
            return JsonResponse({"error": "Failed to generate Excel"}, status=500)
        if not os.path.exists(highlighted_path):
            sys.stdout = old_stdout
            return JsonResponse({"error": "Failed to generate PDF"}, status=500)

        total_members = sum(r["quantity"] for r in results)
        total_weight = sum(r["total_weight"] for r in results)
        processing_time = time.time() - start_time

        print(f"\n{'='*70}")
        print(f"✅ SUCCESS")
        print(f"{'='*70}")
        print(f"Members: {total_members}")
        print(f"Types: {len(results)}")
        print(f"Weight: {total_weight:,.0f} lbs")
        print(f"Time: {processing_time:.1f}s")
        print(f"{'='*70}\n")

        # Restore stdout and capture output
        sys.stdout = old_stdout
        console_output = console_capture.getvalue()

        return JsonResponse(
            {
                "success": True,
                "summary": {
                    "total_members": total_members,
                    "total_types": len(results),
                    "total_weight_lbs": int(total_weight),
                    "total_weight_tons": round(total_weight / 2000, 2),
                    "processing_time": f"{processing_time:.1f}s",
                },
                "files": {"excel": excel_filename, "pdf": highlighted_filename},
                "console_output": console_output,
            }
        )

    except Exception as e:
        sys.stdout = old_stdout
        console_output = console_capture.getvalue()
        
        import traceback
        error_details = traceback.format_exc()
        print(f"\n❌ ERROR:\n{error_details}\n", file=sys.stderr)

        return JsonResponse(
            {
                "error": f"Processing failed: {str(e)}",
                "details": error_details if settings.DEBUG else None,
                "console_output": console_output,
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