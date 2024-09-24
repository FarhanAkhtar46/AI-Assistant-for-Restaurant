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
from datetime import timezone
import pytz
from datetime import time
from datetime import datetime, timedelta
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

    def get_events_for_day(self, event_datetime):
        """Fetches all events on the requested day in the correct timezone (IST -> UTC)."""
        creds = self.get_credentials()
        service = build("calendar", "v3", credentials=creds)
        
        # Ensure `event_datetime` is timezone-aware, defaulting to IST if it's naive
        ist = pytz.timezone('Asia/Kolkata')
        if event_datetime.tzinfo is None:
            event_datetime = ist.localize(event_datetime)
        else:
            # Convert the event datetime to IST
            event_datetime = event_datetime.astimezone(ist)
        
        # Get start and end of the day in IST
        start_of_day_ist = event_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_ist = event_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convert IST times to UTC
        start_of_day_utc = start_of_day_ist.astimezone(pytz.utc)
        end_of_day_utc = end_of_day_ist.astimezone(pytz.utc)
        
        # Format the times for the Google Calendar API in RFC3339 format
        start_of_day_utc_str = start_of_day_utc.isoformat()
        end_of_day_utc_str = end_of_day_utc.isoformat()
        
        print(f"Checking events from {start_of_day_utc_str} to {end_of_day_utc_str} (UTC)")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day_utc_str,
            timeMax=end_of_day_utc_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])

    def check_availability(self, requested_start_time, requested_end_time):
        """Check if the requested time is available."""
        
        # Define IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        
        # Ensure requested times are timezone-aware
        if requested_start_time.tzinfo is None:
            requested_start_time = ist.localize(requested_start_time)
        else:
            requested_start_time = requested_start_time.astimezone(ist)
        
        if requested_end_time.tzinfo is None:
            requested_end_time = ist.localize(requested_end_time)
        else:
            requested_end_time = requested_end_time.astimezone(ist)

        # Fetch events for the requested day
        events = self.get_events_for_day(requested_start_time)

        for event in events:
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            event_end = event['end'].get('dateTime', event['end'].get('date'))

            # Convert event times to datetime objects in IST timezone
            event_start = datetime.fromisoformat(event_start).astimezone(ist)
            event_end = datetime.fromisoformat(event_end).astimezone(ist)

            # Log for debugging
            print(f"Event '{event['summary']}' starts at {event_start} and ends at {event_end}")
            print(f"Checking against requested start: {requested_start_time} and end: {requested_end_time}")

            # Check if the requested time overlaps with an existing event
            if requested_start_time < event_end and requested_end_time > event_start:
                print(f"Conflict detected with event: '{event['summary']}'")
                return False, event['summary']  # Time conflict with this event
        
        return True, None  # No conflict, time is available


    def create_event(self):
        """
        Creates an event on Google Calendar if the requested time is available.
        """
        try:
            # Convert the string to a datetime object
            event_datetime = datetime.fromisoformat(self.event_datetime)
            requested_start_time = event_datetime
            requested_end_time = event_datetime + timedelta(hours=1)

            # Check if the requested time is available
            is_available, conflicting_event = self.check_availability(requested_start_time, requested_end_time)
            
            if not is_available:
                return f"Time slot unavailable due to event: '{conflicting_event}'. Please choose another time."

            creds = self.get_credentials()
            service = build("calendar", "v3", credentials=creds)
            
            event = {
                'summary': self.event_name,
                'description': self.event_description,
                'start': {
                    'dateTime': requested_start_time.isoformat(),
                    'timeZone': 'IST',
                },
                'end': {
                    'dateTime': requested_end_time.isoformat(),
                    'timeZone': 'IST',
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            return f"Event created successfully. Event ID: {event.get('id')}"

        except HttpError as error:
            return f"An error occurred: {error}"
    
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
            event_name = "Test 101"
            calendar_tool = CalendarTool(event_name, booking_date_iso)
            booking_confirmation = calendar_tool.create_event()
            return booking_confirmation
        else:
            return "I couldn't understand the date and time. Could you please specify it again?"

    def _extract_date_time_from_query(self, query):
        """
        Extracts the date and time from a user query using natural language processing via dateparser.
        Ensures correct timezone handling (IST).
        """
        # Define the IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        
        query = query.lower().strip()  # Convert to lowercase for consistency

        # Parse the natural language date and time using dateparser
        parsed_datetime = dateparser.parse(query, settings={'PREFER_DATES_FROM': 'future', 'TIMEZONE': 'Asia/Kolkata'})

        # If `dateparser` doesn't recognize the time, manually search for time and add it
        if parsed_datetime is None or parsed_datetime.time() == datetime.min.time():
            # Handle cases like "tomorrow 7:30 pm" by manually searching for the time
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', query)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                period = time_match.group(3).lower()
                
                # Adjust for AM/PM
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0

                # Create the correct `time` object
                booking_time = time(hour, minute)  # Use datetime.time()

                # Set parsed_datetime for "tomorrow" if needed
                if "tomorrow" in query:
                    tomorrow = datetime.now(ist).date() + timedelta(days=1)
                    parsed_datetime = datetime.combine(tomorrow, booking_time)
                elif "today" in query:
                    today = datetime.now(ist).date()
                    parsed_datetime = datetime.combine(today, booking_time)
        
        # If parsing succeeded, convert to IST timezone
        if parsed_datetime:
            parsed_datetime_ist = parsed_datetime.astimezone(ist)
            print(f"Extracted and parsed date-time (IST): {parsed_datetime_ist}")
            return parsed_datetime_ist
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