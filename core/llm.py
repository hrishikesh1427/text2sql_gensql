# Handles your custom LLM endpoint as an OpenAI-compatible client
from openai import OpenAI

LLM_API_1 = OpenAI(
    api_key="sandlogic",     # your key
    base_url="http://45.194.2.204:3535/v1"   # custom LLM server
)
