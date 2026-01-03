"""
Views for Material Takeoff App
"""
import os
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from collections import Counter

# Import your exact AI code
from .core import (
    extract_ocr, analyze_openai, analyze_gemini,
    reconcile, create_highlighted_pdf, create_excel
)

from django.http import HttpResponse

def index(request):
    """Main page"""
    # Serve HTML directly without template processing
    html = '''<!DOCTYPE html>
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
            max-width: 600px;
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
        <p class="subtitle">Upload your structural drawing PDF and get instant takeoff analysis</p>
        
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
            results.style.display = 'none';
            error.style.display = 'none';
            processBtn.disabled = true;
            
            try {
                const response = await fetch('/process/', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Show results
                    document.getElementById('totalMembers').textContent = data.summary.total_members;
                    document.getElementById('totalTypes').textContent = data.summary.total_types;
                    document.getElementById('totalWeight').textContent = 
                        `${data.summary.total_weight_lbs.toLocaleString()} lbs (${data.summary.total_weight_tons} tons)`;
                    
                    document.getElementById('downloadExcel').href = 
                        `/download/excel/${data.files.excel}/`;
                    document.getElementById('downloadPdf').href = 
                        `/download/pdf/${data.files.pdf}/`;
                    
                    results.style.display = 'block';
                } else {
                    showError(data.error || 'Processing failed');
                }
            } catch (err) {
                showError('Network error: ' + err.message);
            } finally {
                loading.style.display = 'none';
                processBtn.disabled = false;
            }
        });
        
        function showError(message) {
            error.textContent = message;
            error.style.display = 'block';
        }
    </script>
</body>
</html>'''
    return HttpResponse(html)

# def upload(request):
#     return HttpResponse("Upload page")

@csrf_exempt
def process_pdf(request):
    """Process uploaded PDF using AI"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    if 'pdf_file' not in request.FILES:
        return JsonResponse({'error': 'No PDF file uploaded'}, status=400)
    
    pdf_file = request.FILES['pdf_file']
    
    # Validate file
    if not pdf_file.name.endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files allowed'}, status=400)
    
    try:
        # Save uploaded file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{pdf_file.name}"
        pdf_path = os.path.join(settings.MEDIA_ROOT, filename)
        
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        
        with open(pdf_path, 'wb+') as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        
        # Generate output filenames
        base_name = os.path.splitext(filename)[0]
        excel_filename = f"{base_name}_TAKEOFF.xlsx"
        highlighted_filename = f"{base_name}_HIGHLIGHTED.pdf"
        
        excel_path = os.path.join(settings.MEDIA_ROOT, excel_filename)
        highlighted_path = os.path.join(settings.MEDIA_ROOT, highlighted_filename)
        
        # Get API keys from settings
        openai_key = settings.OPENAI_API_KEY
        gemini_key = settings.GEMINI_API_KEY
        
        # Run AI processing (your exact code)
        print("📋 OCR Extraction...")
        ocr_data = extract_ocr(pdf_path)
        ocr_total = sum(sum(c.values()) for c in ocr_data['counts'].values())
        print(f"   Found {ocr_total} members via OCR")
        
        print("🤖 OpenAI Analysis...")
        openai_counts = analyze_openai(pdf_path, openai_key) if openai_key else Counter()
        print(f"   OpenAI found {len(openai_counts)} types")
        
        print("🔮 Gemini Analysis...")
        gemini_counts = analyze_gemini(pdf_path, gemini_key) if gemini_key else Counter()
        print(f"   Gemini found {len(gemini_counts)} types")
        
        print("⚙️ Generating outputs...")
        results = reconcile(ocr_data, openai_counts, gemini_counts)
        create_highlighted_pdf(pdf_path, results, highlighted_path)
        create_excel(results, excel_path, pdf_path)
        
        # Calculate summary
        total_members = sum(r['quantity'] for r in results)
        total_weight = sum(r['total_weight'] for r in results)
        
        return JsonResponse({
            'success': True,
            'summary': {
                'total_members': total_members,
                'total_types': len(results),
                'total_weight_lbs': int(total_weight),
                'total_weight_tons': round(total_weight / 2000, 2)
            },
            'files': {
                'excel': excel_filename,
                'pdf': highlighted_filename
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Processing failed: {str(e)}'}, status=500)

def download_file(request, file_type, filename):
    """Download generated files"""
    file_path = os.path.join(settings.MEDIA_ROOT, filename)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    return FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=filename
    )