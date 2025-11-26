import base64
from pathlib import Path

from openai import OpenAI


class VLMClient:
    """
    Vision-Language Model client used for:
    - Deciding next UI action from screenshot + text goal/subtask.
    - Evaluating visual assertions from screenshot + text assertion.

    Uses the OpenAI Responses API with image input.
    Relies on OPENAI_API_KEY in the environment (or .env via python-dotenv).
    """

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device  # kept for compatibility if you ever switch to local models
        self.client = OpenAI()

    def analyze(self, image_path: str, prompt: str) -> str:
        """
        Given an image path and text prompt, return the model's text answer.

        Sends the screenshot as a base64-encoded data URL combined with
        the textual prompt, using the OpenAI Responses API.
        """
        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Image not found at {img_path}")

        with img_path.open("rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.responses.create(
            model=self.model_name,
            input=[
                {
                    "role": "user",
                    "content": [
                        # Text part: your instructions, goal, subtask, JSON schema, etc.
                        {"type": "input_text", "text": prompt},
                        # Image part: screenshot as data URL
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{b64_image}",
                        },
                    ],
                }
            ],
        )

        return response.output_text
