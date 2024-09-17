from flask import Flask, request, jsonify
import requests
import openai
import logging

app = Flask(__name__)

# Directly set API keys in the code
openai.api_key = ''
erm_api_key = ''

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_categories_from_openai(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": (
                        "Classify the following text into one of the following categories: "
                        "Bakery Operations, Occupational Health, Construction Safety, Electrical Safety, "
                        "Safety Management Systems, CalOSHA, Compressed Gas Safety, High-Hazard Work, "
                        "Lifting Operations and Material Handling, Driving Safety / Fleet Safety, "
                        "Emergency Planning / Response, Fire Safety, Equipment Safety, Environmental, "
                        "Powered Industrial Vehicles, Others. Also, provide a brief description or footprint for the category.\n\n"
                        f"Text to categorize: {text}"
                    )
                }
            ],
            max_tokens=4000,
            temperature=0.3
        )

        content = response.choices[0].message['content'].strip()
        logger.info(f"OpenAI response: {content}")
        
        lines = content.split('\n')
        category = lines[0].strip()
        footprints = [line.strip() for line in lines[1:] if line.strip()]
        
        return {
            "Category": category,
            "footprints": footprints
        }

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {
            "Category": "Unknown",
            "footprints": []
        }

def extract_text_fields(observations):
    prompt_values_and_types = []
    for observation in observations:
        for res in observation.get('responses', []):
            prompt_value = res.get('value')
            prompt_type = res.get('type')
            if prompt_value and prompt_type in ["Text", "Text Field"]:
                prompt_values_and_types.append({"value": prompt_value, "type": prompt_type})
    return [item['value'] for item in prompt_values_and_types]  # Return only text values

@app.route('/process_assessment', methods=['POST'])
def process_assessment():
    assessment_id = request.json.get('assessment_id')
    
    if not assessment_id:
        return jsonify({"error": "assessment_id is required"}), 400

    try:
        headers = {"Authorization": f"Bearer {erm_api_key}"}
        assessment_url = f"https://de.ermassess.com/gateway/v1/assessments/{assessment_id}"
        response = requests.get(assessment_url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch assessment data"}), response.status_code
        
        data = response.json().get('data', {})
        observations = data.get("observations", [])

        # Extract text fields from the observations
        text_fields = extract_text_fields(observations)

        # Initialize a dictionary to accumulate categories and footprints
        categorized_texts = {}

        # Categorize each text field
        for text in text_fields:
            if text.strip():  # Ensure text is not empty
                try:
                    result = get_categories_from_openai(text)
                    category = result['Category']
                    footprints = result['footprints']

                    if category not in categorized_texts:
                        categorized_texts[category] = {
                            "Category": category,
                            "Value": 0,
                            "footprints": []
                        }

                    categorized_texts[category]['Value'] += 1
                    categorized_texts[category]['footprints'].extend(footprints)
                
                except Exception as e:
                    logger.error(f"Error categorizing text: {e}")

        # Format the response
        formatted_response = list(categorized_texts.values())

        return jsonify(formatted_response)

    except Exception as e:
        logger.error(f"Processing error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
