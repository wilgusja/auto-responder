"""
- This script formats a raw free-text brand description into a structured prompt format using OpenAI's API.
- It uses the OpenAI API to generate a structured prompt that includes context about the brand, guidelines for tone and style, and any specific instructions.
- It is designed to be used in a Google Sheets or CSV context, where the output can be safely stored with literal newline characters.
- This is useful for onboarding new brands or updating existing ones in a structured way.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def format_brand_context(raw_input: str) -> str:
    """
    Converts a raw free-text brand description into a structured prompt format
    using literal \n characters for safe storage in Sheets or CSVs.
    """
    system_prompt = (
        "You will take raw input from a client about their brand and rewrite it into a structured system prompt "
        "for an AI autoresponder.\n\n"
        "The structured format should include:\n\n"
        "Context:\n"
        "- What the brand sells\n"
        "- Key products or bundles\n"
        "- Target customer\n\n"
        "Guidelines:\n"
        "- Tone of voice\n"
        "- Anything to avoid (hashtags, medical claims, etc.)\n"
        "- Style (concise, emoji use, etc.)\n\n"
        "Format the result using literal \\n characters for newlines so it can be stored safely in CSV or Google Sheets."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_input}
        ]
    )

    return response.choices[0].message.content.strip()


# Example usage:
if __name__ == "__main__":
    raw = (
        "We sell two supplements — Boost for energy and Recover for rest. They’re sold separately or in a bundle called the Vitality Pack. "
        "We’re a friendly brand, a little bit casual, but not too silly. Don’t use hashtags or emojis in DMs, please."
    )
    structured = format_brand_context(raw)
    print("Formatted Prompt:\n")
    print(structured)
