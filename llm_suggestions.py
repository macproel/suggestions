import sqlite3
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from fastapi.responses import JSONResponse, FileResponse
from suggestion_map import suggestions_map


# Initialize OpenAI API Key
api_key = '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'
client = OpenAI(api_key=api_key)

# Create the FastAPI app
app = FastAPI()
    
# SQLite database connection setup
def get_db_connection():
    conn = sqlite3.connect("suggestions.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create table if it doesn't exist
def initialize_db():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS suggestions (
        keywords TEXT UNIQUE,
        suggestions TEXT
    )
    """)
    conn.commit()
    conn.close()

# Pydantic model to define request format
class MessageRequest(BaseModel):
    message: str

# Function to get chat suggestions from the database
def get_suggestions_from_db(message: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT suggestions FROM suggestions WHERE keywords LIKE ?", ('%' + message + '%',))
    result = cursor.fetchone()
    conn.close()
    return result['suggestions'] if result else None

# Function to save suggestions to the database
def save_suggestions_to_db(keywords: str, suggestions: str):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO suggestions (keywords, suggestions) VALUES (?, ?)", (keywords, suggestions))
    conn.commit()
    conn.close()

# Function to get chat suggestions
def get_chat_suggestions(message: str) -> List[str]:
    # Convert message to lowercase for case-insensitive matching
    message = message.lower()

    # Check for matching suggestions in the database
    suggestions_from_db = get_suggestions_from_db(message)
    if suggestions_from_db:
        return suggestions_from_db.split(",")  # Return as a list
    
    # Check for matching keywords in hardcoded suggestions_map (if any)
    for key in suggestions_map:
        if isinstance(key, tuple):
            for sub_key in key:
                if sub_key in message:
                    return suggestions_map[key]
        elif isinstance(key, str) and key in message:
            return suggestions_map[key]
    
    # If no suggestions are found in the map or db, call OpenAI API
    return generate_suggestions_from_openai(message)

def extract_list(suggestions: str) -> List[str]:
    # Extract strings within double quotes and store in a list
    extracted_list = []
    current_string = ""
    in_quotes = False

    for char in suggestions:
        if char == '"':
            in_quotes = not in_quotes
            if not in_quotes and current_string:
                extracted_list.append(current_string)
                current_string = ""
        elif in_quotes:
            current_string += char

    return extracted_list


def generate_suggestions_from_openai(message):
    try:
        # Use OpenAI API with `ChatCompletion` to generate small code snippets
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Please provide concise and specific information about the project"},
                {"role": "user", "content": f"Generate three suggestions for the message: '{message}'"}
            ],
            model="gpt-4o-mini"
        )
        print("___________________________________________________________________________")
        print("api got called")
        print("___________________________________________________________________________")
        consolidated_suggestions = chat_completion.choices[0].message.content        
        suggestions = extract_list(consolidated_suggestions)
        
        save_suggestions_to_db(message, ",".join(suggestions))

        return suggestions
    except Exception as e:
        print(f"Error generating suggestions from OpenAI: {e}")
        return []


# Initialize the database on startup
initialize_db()

# POST endpoint to handle incoming messages and return suggestions
@app.post("/get_suggestions/")
async def get_suggestions(request: MessageRequest):
    message = request.message
    suggestions = get_chat_suggestions(message)
    if not suggestions:
        raise HTTPException(status_code=404, detail="Suggestions not found")
    return {"suggestions": suggestions}
