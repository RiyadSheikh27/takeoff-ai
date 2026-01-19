# test_ai_keys.py

# -----------------------------
# 1️⃣ OpenAI GPT Test
# -----------------------------
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key="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")

    # Simple test: list available models
    models = openai_client.models.list()
    print("✅ OpenAI GPT key works! Available models:")
    for model in models.data[:5]:  # just show first 5
        print(f"   - {model.id}")
except Exception as e:
    print(f"❌ OpenAI GPT key failed: {e}")


# -----------------------------
# 2️⃣ Google Gemini Test
# -----------------------------
try:
    import google.generativeai as genai

    genai.configure(api_key="AIzaSyAvkvp6y0qg8SIHoy9Y0_TDXyohjgP19vI")
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    response = model.generate_content("Say OK")
    print("✅ Gemini key works!")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Gemini key failed: {e}")
