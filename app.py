from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
from dotenv import load_dotenv
from pypdf import PdfReader
import io
import time

load_dotenv()

app = Flask(__name__)
CORS(app)

SYSTEM_PROMPT = """You are an expert O Level Chemistry tutor helping Sec 4 students in Singapore.
When given chemistry notes, you must respond ONLY with a valid JSON object in this exact format:
{
  "summary": "A clear 3-5 sentence summary of the notes",
  "keypoints": "• Key point 1\\n• Key point 2\\n• Key point 3\\n(5-8 bullet points of the most important concepts)",
  "questions": "Q1: [question]\\nA1: [answer]\\n\\nQ2: [question]\\nA2: [answer]\\n\\nQ3: [question]\\nA3: [answer]\\n(3-5 practice questions with answers based on O Level style)"
}
Do not include anything outside the JSON. Keep language simple and exam-focused."""

def call_ai(notes_text):
    for attempt in range(3):
        try:
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {os.getenv("OPENROUTER_API_KEY")}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'openrouter/free',
                    'max_tokens': 1500,
                    'messages': [
                        {'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': f'Analyse these chemistry notes:\n\n{notes_text}'}
                    ]
                },
                timeout=30
            )

            data = response.json()
            print('RESPONSE:', data)

            if 'choices' not in data:
                raise Exception(f"API error: {data}")

            content = data['choices'][0]['message']['content']
            print('CONTENT:', content)
            # Parse JSON from response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON if model added extra text
                start = content.find('{')
                end = content.rfind('}') + 1
                result = json.loads(content[start:end])

            return result

        except Exception as e:
            print(f'Attempt {attempt + 1} failed: {e}')
            time.sleep(1)

    raise Exception('Failed to get response after 3 attempts')


@app.route('/analyse', methods=['POST'])
def analyse_text():
    notes_text = request.json.get('text', '')
    if not notes_text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        result = call_ai(notes_text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyse-pdf', methods=['POST'])
def analyse_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF uploaded'}), 400

    pdf_file = request.files['pdf']

    try:
        # Extract text from PDF
        reader = PdfReader(io.BytesIO(pdf_file.read()))
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'

        if not text.strip():
            return jsonify({'error': 'Could not extract text from PDF'}), 400

        result = call_ai(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
