import openai

openai.api_key = ""

try:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, world!"}
        ]
    )
    print(response['choices'][0]['message']['content'].strip())
except Exception as e:
    print(f"Error: {e}")

