import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import Field
from ..base_tool import BaseTool
from utils import SCOPES
from datetime import timezone


class CalendarTool:
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
                    "path_to_your_credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def get_events_for_day(self, event_datetime):
        """Fetches all events on the requested day."""
        creds = self.get_credentials()
        service = build("calendar", "v3", credentials=creds)
        
        start_of_day = event_datetime.replace(hour=0, minute=0, second=0).isoformat() + 'Z'  # Start of the day in UTC
        end_of_day = event_datetime.replace(hour=23, minute=59, second=59).isoformat() + 'Z'  # End of the day in UTC
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    
    def check_availability(self, requested_start_time, requested_end_time):
        """Check if the requested time is available."""
        events = self.get_events_for_day(requested_start_time)

        for event in events:
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            event_end = event['end'].get('dateTime', event['end'].get('date'))

            # Convert event times to datetime objects
            event_start = datetime.datetime.fromisoformat(event_start)
            event_end = datetime.datetime.fromisoformat(event_end)

            # Check if the requested time overlaps with an existing event
            if requested_start_time < event_end and requested_end_time > event_start:
                return False, event['summary']  # Time conflict with this event
        
        return True, None  # No conflict, time is available
    
    def create_event(self, event_start_time, event_end_time):
        """Creates an event on Google Calendar."""
        try:
            creds = self.get_credentials()
            service = build("calendar", "v3", credentials=creds)

            event = {
                'summary': self.event_name,
                'description': self.event_description,
                'start': {
                    'dateTime': event_start_time.isoformat(),
                    'timeZone': 'IST',
                },
                'end': {
                    'dateTime': event_end_time.isoformat(),
                    'timeZone': 'IST',
                },
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            return f"Event created successfully. Event ID: {event.get('id')}"

        except HttpError as error:
            return f"An error occurred: {error}"

    def book_table(self):
        """Main method to check availability and book a table."""
        requested_start_time = datetime.datetime.fromisoformat(self.event_datetime)
        requested_end_time = requested_start_time + datetime.timedelta(hours=1)

        available, conflicting_event = self.check_availability(requested_start_time, requested_end_time)
        
        if available:
            return self.create_event(requested_start_time, requested_end_time)
        else:
            return f"The requested time is occupied by another event: {conflicting_event}. Please choose another time."
