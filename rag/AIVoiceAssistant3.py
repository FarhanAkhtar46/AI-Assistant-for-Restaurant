from qdrant_client import QdrantClient
from llama_index.llms.openai import OpenAI
from llama_index.core import SimpleDirectoryReader
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import ServiceContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.storage.storage_context import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
import os
import re
import warnings
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from utils import SCOPES
import dateparser
from pydantic import Field
warnings.filterwarnings("ignore")
load_dotenv()
from tools.base_tool import BaseTool
# CalendarTool for handling table booking events
class CalendarTool():
    
    
        
    
    def __init__(self, event_name, event_datetime, event_description=""):
        self.event_name = event_name
        self.event_datetime = event_datetime
        self.event_description = event_description

    def get_credentials(self):
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "C:/Users/farhan.akhtar/Developer/Restro-voice-bot/tools/calander/credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def create_event(self):
        try:
            creds = self.get_credentials()
            service = build("calendar", "v3", credentials=creds)

            event_datetime = datetime.datetime.fromisoformat(self.event_datetime)

            event = {
                'summary': self.event_name,
                'description': self.event_description,
                'start': {
                    'dateTime': event_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': (event_datetime + datetime.timedelta(hours=1)).isoformat(),
                    'timeZone': 'UTC',
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            return f"Event created successfully. Event ID: {event.get('id')}"

        except HttpError as error:
            return f"An error occurred: {error}"

    def run(self):
        return self.create_event()
    
# AIVoiceAssistant for interacting with the user
class AIVoiceAssistant:
    
    
    def __init__(self):
        self._client = QdrantClient(
            url="https://eb5494d7-2826-4710-8d85-399256878ad3.europe-west3-0.gcp.cloud.qdrant.io:6333", 
            api_key="ab5Skkx4ISVB_Kucp2C5DGxTvz-w9FNxyyNyroCInpo8YHXX7oPAOw"
        )
        
        Settings.llm = OpenAI(model="gpt-4o", api_key=os.getenv('OPENAI_API_KEY'))
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-ada-002", api_key=os.getenv('OPENAI_API_KEY'))
        self._index = None
        self._create_kb()
        self._create_chat_engine()

    def _create_chat_engine(self):
        memory = ChatMemoryBuffer.from_defaults(token_limit=2500)
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
            print("Knowledgebase created successfully!")
        except Exception as e:
            print(f"Error while creating knowledgebase: {e}")

    def interact_with_llm(self, customer_query):
        # customer_query = "Book a table for tomorrow 12 pm."
        # Detect if the query is about table booking
        if self._is_table_booking_request(customer_query):
            return self._handle_table_booking(customer_query)
        else:
            AgentChatResponse = self._chat_engine.chat(customer_query)
            return AgentChatResponse.response
        
    

    def _is_table_booking_request(self, customer_query):
        # Basic regex to detect table booking requests
        booking_keywords = re.compile(r'book.*table|reserve.*table', re.IGNORECASE)
        return bool(booking_keywords.search(customer_query))

        
    def _handle_table_booking(self, customer_query):
        """
        Handle table booking by extracting the date and time from the query and 
        creating an event in Google Calendar.
        """
        # Extract date and time from the user's query
        booking_date = self._extract_date_time_from_query(customer_query)
        if booking_date:
            # Convert the datetime object to ISO format string before passing
            booking_date_iso = booking_date.isoformat()
            event_name = "Table Reservation at Ranchi's Kitchen"
            calendar_tool = CalendarTool(event_name, booking_date_iso)
            booking_confirmation = calendar_tool.create_event()
            return booking_confirmation
        else:
            return "I couldn't understand the date and time. Could you please specify it again?"

    def _extract_date_time_from_query(self, query):
        """
        Extracts the date and time from a user query using natural language processing via dateparser.
        Handles common date/time phrases and ensures correct parsing.
        """
        query = query.lower()  # Convert to lowercase for consistency
        
        # Optional: Remove irrelevant words (e.g., "book a table", "reserve a table")
        query = re.sub(r"(book.*table|reserve.*table)", "", query).strip()
        
        # Parse the natural language date and time using dateparser with extra settings
        parsed_datetime = dateparser.parse(query, settings={'PREFER_DATES_FROM': 'future'})
        
        # Fallback for specific cases if dateparser fails
        if not parsed_datetime:
            # Check for "tomorrow" or "today" and parse time separately
            if "tomorrow" in query:
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', query)
                if time_match:
                    time_str = f"{time_match.group(1)} {time_match.group(2)}"
                    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
                    parsed_datetime = datetime.datetime.combine(tomorrow, datetime.time())
                    parsed_datetime += datetime.timedelta(hours=int(time_match.group(1)))
            elif "today" in query:
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', query)
                if time_match:
                    time_str = f"{time_match.group(1)} {time_match.group(2)}"
                    today = datetime.date.today()
                    parsed_datetime = datetime.datetime.combine(today, datetime.time())
                    parsed_datetime += datetime.timedelta(hours=int(time_match.group(1)))
        
        if parsed_datetime:
            print(f"Extracted and parsed date-time: {parsed_datetime}")
            return parsed_datetime
        else:
            return None


    @property
    def _prompt(self):
        return """
            You are a voice assistant for Ranchi's Kitchen, a restaurant located at M G road, Ranchi, Jharkhand. 
            The hours are 10 AM to 11 PM daily, but they are closed on Sundays.
            Start with greeting as 'Hello, this is Jane from Ranchi's Kitchen. How can I assist you today?'
            Ranchi's Kitchen provides both dine-in and take-away services to the local community.

            
            
            
            2. For online orders:
            - Ask the customer for their full name.
            - Collect their contact number.
            - Ask for the items they'd like to order from the menu, saving them into the order_details variable.

            - Be sure to be funny and witty!
            - Keep all responses short, simple, and friendly.
        """

