import os
from flask import Flask, render_template, request, jsonify
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from secrets.env
load_dotenv('secrets.env')

# Access environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE_URL = "https://api.openai.com/v1"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

MODEL_NAME = "gpt-4o-2024-08-06"

app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=OPENAI_API_KEY, 
    base_url=API_BASE_URL
)

# Helper function to generate Overpass API query using GPT-4o
def get_overpass_api_query(user_query, regions):
    # Create a prompt with the user query and the regions data  
    prompt_content = f"""
    You are an expert OpenStreetMap API assistant. Convert the user's natural language query into a valid Overpass API query that can be used to answer the question. The user's query is:
    "{user_query}"
    
    The user has specified regions of interest, described as follows:
    {regions}

    Only respond with the Overpass query itself, not any additional text. You should not output any Python code, just the Overpass query. You should never output any newlines or line breaks in the response.
    """
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": prompt_content.strip()
            }
        ],
        stream=False
    )
    
    # Extract the generated Overpass query from the response
    overpass_query = response.choices[0].message.content
    if "```" in overpass_query:
        overpass_query = overpass_query.replace("```", "")
    
    return overpass_query

# Helper function to query Overpass API
def query_overpass(overpass_query):
    payload = {"data": overpass_query}
    response = requests.post(OVERPASS_API_URL, data=payload)
    return response.json()

# Route to render the main HTML page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle query submission from the client
@app.route('/submit_query', methods=['POST'])
def submit_query():
    data = request.get_json()
    
    # Extract natural language query and regions from the client's JSON data
    user_query = data.get('query', '')
    regions = data.get('regionOfInterest', [])
    
    if not user_query or not regions:
        return jsonify({"error": "Both query and regionOfInterest are required"}), 400
    
    print(data)

    # Generate Overpass API query using GPT-4o
    try:
        overpass_query = get_overpass_api_query(user_query, regions)
        print(f"Generated Overpass Query: {overpass_query}")
    except Exception as e:
        print(f"Error generating Overpass query: {e}")
        return jsonify({"error": "Failed to generate Overpass query", "details": str(e)}), 500

    # Send the generated Overpass query to the Overpass API
    try:
        overpass_response = query_overpass(overpass_query)
        print(overpass_response)

        if "elements" in overpass_response and len(overpass_response["elements"]) > 0:
            
            # format the elements so that they can be displayed on the frontend
            new_array = []
            for element in overpass_response["elements"]:
                new_element = {}
                new_element["lat"] = element.get("lat", None)
                new_element["lng"] = element.get("lon", None)
                new_element["title"] = element.get("tags", {}).get("name", "Unknown")
                new_element["tags"] = element.get("tags", {})
                new_array.append(new_element)

            return {"response": new_array}
        else:
            return {"error": "No elements found in the Overpass API response"}, 404
    except Exception as e:
        return jsonify({"error": "Failed to fetch data from Overpass API", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
