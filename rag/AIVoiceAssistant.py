from qdrant_client import QdrantClient
from llama_index.llms.openai import OpenAI # Assuming there's a wrapper like this, otherwise import OpenAI directly
from llama_index.core import SimpleDirectoryReader
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import ServiceContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.storage.storage_context import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
import os



import warnings
warnings.filterwarnings("ignore")
load_dotenv()

# Load the configuration from the .env file

class AIVoiceAssistant:
    def __init__(self):
        self._qdrant_url = "http://localhost:6333"
        self._client = QdrantClient(url=self._qdrant_url, prefer_grpc=False)
        
        # Replace Ollama with OpenAI and specify the model to GPT-4
        Settings.llm = OpenAI(model="gpt-4o", api_key=os.environ.get('OPENAI_API_KEY')) # Ensure you have the correct import and API key
        
        # self._service_context = ServiceContext.from_defaults(llm=self._llm, embed_model="local")
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-ada-002", 
                                               api_key=os.getenv('OPENAI_API_KEY'))
        self._index = None
        self._create_kb()
        self._create_chat_engine()

    def _create_chat_engine(self):
        memory = ChatMemoryBuffer.from_defaults(token_limit=1500)
        self._chat_engine = self._index.as_chat_engine(
            chat_mode="context",
            memory=memory,
            system_prompt=self._prompt,
        )

    def _create_kb(self):
        try:
            data = SimpleDirectoryReader(input_dir="./rag/").load_data()
            
            vector_store = QdrantVectorStore(client=self._client, collection_name="kitchen_db1")
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            self._index = VectorStoreIndex.from_documents(data, storage_context=storage_context)
            # self._index = VectorStoreIndex.from_documents(
            #     documents, service_context=self._service_context, storage_context=storage_context
            # )
            print("Knowledgebase created successfully!")
        except Exception as e:
            print(f"Error while creating knowledgebase: {e}")

    def interact_with_llm(self, customer_query):
        AgentChatResponse = self._chat_engine.chat(customer_query)
        answer = AgentChatResponse.response
        return answer

    @property
    def _prompt(self):
        return """
            You are a voice assistant for Ranchi's Kitchen, a restaurant located at M G road, Ranchi, Jharkhand. The hours are 10 AM to 11 PM daily, but they are closed on Sundays.
Start with greeting as 'Hello, this is Jane from Ranchi's Kitchen . How can I assist you today?'
Ranchi's Kitchen provides dine in and take away services to the local Anaheim community. 

When asked about the items in menu and their respective prices, use the "restaurant_file document" from the upload files.

Your task is to gather information from the caller who wish to place an order in following manner:
1. Ask caller for his/her full name .
2. Ask caller for their contact number.
3. Ask caller for their items from the menu and save it into order_details variable.

- Be sure to be kind of funny and witty!
- Keep all your responses short and simple. Use casual language, phrases like "Umm...", "Well...", and "I mean" are preferred.
- This is a voice conversation, so keep your responses short, like in a real conversation. Don't ramble for too long.
            """

# Note:
# - Replace `'your_openai_api_key'` with your actual OpenAI API key.
# - Make sure the necessary OpenAI Python client is installed (e.g., openai-python).
