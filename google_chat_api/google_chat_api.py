import requests
import json
import os
from dotenv import load_dotenv

class google_chat_api:
    def __init__(self):
        load_dotenv()
        try:
            space_url = os.getenv("api_url")
        except Exception as e:
            print(f"An error occurred while loading environment variables: {e}")
        self.space_url = space_url

    def send_message(self, msg):
        headers = {
            "Content-Type": "application/json; charset=UTF-8"
        }

        # Using Cards v2 to force a display name and icon
        body = {
            "cardsV2": [
                {
                    "cardId": "jira_notification_01",
                    "card": {
                        "header": {
                            "title": "New request created",
                        },
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "textParagraph": {
                                            "text": msg
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }

        response = requests.post(
            self.space_url, 
            data=json.dumps(body), 
            headers=headers, 
            timeout=5
        )
        return response.status_code
    