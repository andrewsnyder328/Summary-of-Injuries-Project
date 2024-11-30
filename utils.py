import io
import base64
import json
import logging

import openai
from openai import OpenAI

from config import (
    EXTRACTION_MODEL,
    COMBINATION_MODEL,
    GPT4O_MAX_OUTPUT_TOKENS,
    TEMPERATURE,
    RESPONSE_FORMAT,
)

from prompts import EXTRACTION_SYSTEM_PROMPT, COMBINE_SYSTEM_PROMPT

from dotenv import load_dotenv
load_dotenv()  # Load environment variables, e.g., OpenAI API key

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
    except OpenAIError as e:
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