from openai import OpenAI


class LLMClient:
    """
    Text-only LLM client used for:
    - Converting natural-language test descriptions into structured scenarios.

    Uses the OpenAI Responses API.
    Relies on OPENAI_API_KEY in the environment (or .env via python-dotenv).
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client = OpenAI()  # Reads OPENAI_API_KEY automatically

    def generate(self, prompt: str) -> str:
        """
        Given a text prompt, return the model's text completion.

        The ScenarioGenerator constructs prompts that require the model
        to output ONLY a JSON object as a string.
        """
        response = self.client.responses.create(
            model=self.model_name,
            input=prompt,
        )
        # Combined text output from the response
        return response.output_text
