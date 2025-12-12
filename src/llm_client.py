from openai import OpenAI
import google.generativeai as genai
import json
import logging
import os

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, provider, api_key, model=None):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        
        if self.provider == "openai":
            if not self.model:
                self.model = "gpt-4o"
            self.client = OpenAI(api_key=api_key)
            
        elif self.provider == "gemini":
            if not self.model:
                self.model = "gemini-2.0-flash-exp"
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model)
            
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def generate_question(self, diff_text, difficulty="medium", system_prompt=None, custom_instructions=None):
        extra_instructions = f"- {custom_instructions}" if custom_instructions else ""
        
        default_system_prompt = f"""
You are a code reviewer designed to ensure developers have read their changes.
Generate a {difficulty} multiple-choice question based on the provided code diff.
The question should verify that the developer understands the specific logic changes.
Focus on:
- Validating new values (timeouts, constants).
- Understanding control flow changes.
- Identifying security implications if applicable.
{extra_instructions}

Return ONLY a valid JSON object with this structure:
{{
    "question": "The question text",
    "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C"
    }},
    "correct_answer": "B"
}}
"""
        prompt = system_prompt if system_prompt else default_system_prompt
        
        if self.provider == "openai":
            return self._generate_openai(prompt, diff_text)
        elif self.provider == "gemini":
            return self._generate_gemini(prompt, diff_text)

    def _generate_openai(self, system_prompt, diff_text):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here is the code diff:\n\n{diff_text}"}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return None

    def _generate_gemini(self, system_prompt, diff_text):
        try:
            full_prompt = f"{system_prompt}\n\nHere is the code diff:\n\n{diff_text}"
            response = self.client.generate_content(
                full_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return None
