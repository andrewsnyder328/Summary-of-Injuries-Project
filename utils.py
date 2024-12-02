import io
import base64
import json
import logging
import os

import openai
from openai import OpenAI
from serpapi import GoogleSearch

from config import (
    EXTRACTION_MODEL,
    COMBINATION_MODEL,
    GPT4O_MAX_OUTPUT_TOKENS,
    TEMPERATURE,
    RESPONSE_FORMAT,
)

from prompts import EXTRACTION_SYSTEM_PROMPT, COMBINE_SYSTEM_PROMPT, GENERATE_QUERY_SYSTEM_PROMPT, PARSE_WEB_RESULTS_SYSTEM_PROMPT

from dotenv import load_dotenv
load_dotenv()  # Load environment variables

# Initialize OpenAI client
client = OpenAI()


def encode_image_to_base64(image):
    """Encode a PIL Image to a base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def extract_text_from_image(image, page_number=0):
    """Extract text from an image using the OpenAI API."""
    base64_image = encode_image_to_base64(image)

    messages = [
        {
            "role": "system",
            "content": EXTRACTION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Please process the following image:",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                },
            ],
        },
    ]

    try:
        response = client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=messages,
            response_format=RESPONSE_FORMAT,
            temperature=TEMPERATURE,
            max_tokens=GPT4O_MAX_OUTPUT_TOKENS,
        )
        assistant_message = response.choices[0].message.content.strip()
        return assistant_message
    except openai.APIConnectionError as e:
        print("The server could not be reached")
        print(e.__cause__)
    except openai.RateLimitError as e:
        print("A 429 status code was received; we should back off a bit.")
    except openai.APIStatusError as e:
        print("Another non-200-range status code was received")
        print(e.status_code)
        print(e.response)
    return None


def combine_page_contents(page_contents):
    """Combine extracted page contents into a single markdown output."""
    combine_messages = [
        {
            "role": "system",
            "content": COMBINE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": "Please combine the following page contents into a JSON output:",
        },
        {
            "role": "user",
            "content": json.dumps(page_contents),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=COMBINATION_MODEL,
            messages=combine_messages,
            response_format=RESPONSE_FORMAT,
            temperature=TEMPERATURE,
            max_tokens=GPT4O_MAX_OUTPUT_TOKENS,
        )
        assistant_message = response.choices[0].message.content.strip()
        return assistant_message
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error during content combination: {e}")
        return None


def save_markdown(output_path, markdown_content):
    """Save the markdown content to a file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logging.info(f"Markdown output saved to '{output_path}'.")
    except Exception as e:
        logging.error(f"Error saving markdown file '{output_path}': {e}")


def generate_search_query(markdown_content, document_name):
    """Generate search query and extract information from markdown content using OpenAI GPT-4o."""
    messages = [
        {
            "role": "system",
            "content": GENERATE_QUERY_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Notes:\n{markdown_content}\n\nDocument Name: {document_name}",
        },
    ]

    try:
        response = client.chat.completions.create(
            model=COMBINATION_MODEL,  # Use GPT-4o model
            messages=messages,
            response_format={"type": "json_object"},
            temperature=TEMPERATURE,
            max_tokens=512,  # Adjust as needed
        )
        assistant_message = response.choices[0].message.content.strip()
        result = json.loads(assistant_message)

        # Extract the required information
        date_of_visit = result.get("date_of_visit", "")
        diagnosis = result.get("diagnosis", "")
        reference = result.get("reference", "")
        query = result.get("query", "")

        return {
            "date_of_visit": date_of_visit,
            "diagnosis": diagnosis,
            "reference": reference,
            "query": query,
        }
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error during query generation: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON in query generation: {e}")
    return None


def search_icd10_code(query):
    """Search for ICD-10 code using SerpAPI."""
    params = {
        "q": query,
        "num": 10,  # Number of results
        "api_key": os.getenv("SERPAPI_API_KEY"),
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        # Create a filtered results dictionary
        filtered_results = {}

        # Include the entire 'answer_box' if present
        if 'answer_box' in results:
            filtered_results['answer_box'] = results['answer_box']

        # Include selected fields from 'organic_results'
        if 'organic_results' in results:
            filtered_organic_results = []
            for result in results['organic_results']:
                filtered_result = {}
                for key in ['position', 'title', 'link', 'snippet', 'snippet_highlighted_words', 'cached_page_link', 'source']:
                    if key in result:
                        filtered_result[key] = result[key]
                filtered_organic_results.append(filtered_result)
            filtered_results['organic_results'] = filtered_organic_results

        return filtered_results

    except Exception as e:
        logging.error(f"Error during SerpAPI search: {e}")
        return None


def extract_icd10_code_from_results(results):
    """Extract ICD-10 code from search results using OpenAI GPT-4o."""
    # Convert search results to a string
    results_text = json.dumps(results, indent=2)

    messages = [
        {
            "role": "system",
            "content": PARSE_WEB_RESULTS_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": f"Web Search Results:\n{results_text}",
        },
    ]

    try:
        response = client.chat.completions.create(
            model=COMBINATION_MODEL,  # Use GPT-4o model
            messages=messages,
            response_format={"type": "json_object"},
            temperature=TEMPERATURE,
            max_tokens=256,  # Adjust as needed
        )
        assistant_message = response.choices[0].message.content.strip()
        result = json.loads(assistant_message)
        code = result.get("code", "")
        return code
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API error during ICD-10 code extraction: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON in ICD-10 code extraction: {e}")
    return None
