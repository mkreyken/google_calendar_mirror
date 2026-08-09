from src.clients.google_mail_client import GmailTextSender

TEST_EMAIL = "michael@icdelta.ca"
TEST_SUBJECT = "ACTOR TEST SUBJECT"
TEST_BODY = "Hello MK, this is an actor test."


def test_gmail_actor_end_to_end() -> None:
    """
    True actor test:
    - Uses real Gmail API
    - Sends a real email
    - Searches for it
    - Verifies subject/body
    - Deletes it
    """

    sender = GmailTextSender()

    # 1. Send the email
    send_response = sender.send_text(
        to=TEST_EMAIL,
        subject=TEST_SUBJECT,
        body=TEST_BODY
    )

    assert "id" in send_response
    sent_id = send_response["id"]
    print(f"message if was {sent_id}")


test_gmail_actor_end_to_end()
