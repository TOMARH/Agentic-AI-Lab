import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=api_key)

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    ##input="Explain in one sentence what an AI agent is. respond in hindi"
    input="Bollywood mein Kajol ya naye purane kinhi bhi actors ke najayaz sambandh hue hai. in hindi"
)

print(interaction.output_text)