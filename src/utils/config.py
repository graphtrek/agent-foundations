import getpass
import os

from dotenv import find_dotenv, load_dotenv


def load_config() -> str:
    env_path = find_dotenv()
    if env_path:
        print(f"Loading environment variables from: {env_path}")
        load_dotenv(env_path)
    else:
        print("No .env file found. Please ensure that the .env file exists in the project directory.")      

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key is None:
        print("Please enter your OpenRouter API key:")
        api_key = getpass.getpass("API Key: ")
        os.environ["OPENROUTER_API_KEY"] = api_key

    if api_key and api_key.strip():
        print('OPENROUTER_API_KEY environment variable is set.')
    else:
        print("OPENROUTER_API_KEY environment variable is not set.")

    if os.environ.get("LANGCHAIN_DEBUG") == "true":
        print("LANGCHAIN_DEBUG is set to true. Debugging information will be printed.")
    return api_key