from datetime import datetime, timedelta
from airflow import DAG
from airflow.decorators import task
from airflow.providers.amazon.aws.sensors.sqs import SqsSensor
from airflow.providers.http.hooks.http import HttpHook
from airflow.exceptions import AirflowException
import json

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['youremail@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
with DAG(
    dag_id='sqs_to_webhook_dag',
    default_args=default_args,
    description='A DAG that retrieves messages from SQS and sends them to a webhook',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2024, 4, 1),
    catchup=False,
    tags=['example', 'sqs', 'webhook', 'taskflow'],
) as dag:

    # SQS Sensor Task
    wait_for_sqs_message = SqsSensor(
        task_id='wait_for_sqs_message',
        aws_conn_id='sqs-connection-combopretifier',  # Ensure this matches your Airflow connection
        sqs_queue='https://sqs.us-east-2.amazonaws.com/068064050187/input-notification',  # Replace with your SQS queue URL
        max_messages=10,              # Maximum number of messages to retrieve per batch (up to 10)
        num_batches=1,                # Number of batches to retrieve per poke
        wait_time_seconds=20,         # Long polling duration (seconds)
        poke_interval=30,             # How often to poke the queue (seconds)
        timeout=600,                  # Timeout for the sensor (seconds)
        mode='poke',                  # 'poke' or 'reschedule'
        visibility_timeout=30,        # Visibility timeout for messages
        delete_message_on_reception=True,  # Ensure messages are deleted upon retrieval
    )

    @task
    def process_and_send_to_webhook(messages):
        """
        Task to process SQS messages and send them to a webhook via HTTP POST.
        """
        if not messages:
            print("No messages to process.")
            return

        # Initialize the HTTP Hook
        http_hook = HttpHook(
            method='POST',
            http_conn_id='webhook-test',  # Ensure this matches your Airflow HTTP connection
        )

        # Define the webhook endpoint path if needed
        # For example, if the full URL is used in the connection, you can leave it empty
        # Otherwise, specify the relative path
        endpoint = ''  # e.g., '/path/to/endpoint' if needed

        for message in messages:
            try:
                # Extract message details
                message_id = message.get('MessageId')
                message_body = message.get('Body')

                # Prepare the payload
                payload = {
                    'MessageId': message_id,
                    'Body': message_body,
                }

                # Convert payload to JSON
                payload_json = json.dumps(payload)

                # Send POST request to the webhook
                response = http_hook.run(
                    endpoint=endpoint,
                    data=payload_json,
                    headers={'Content-Type': 'application/json'},
                )

                # Check response status
                if response.status_code != 200:
                    raise AirflowException(
                        f"Failed to send message {message_id} to webhook. "
                        f"Status Code: {response.status_code}, Response: {response.text}"
                    )
                else:
                    print(f"Successfully sent Message ID: {message_id} to webhook.")

            except Exception as e:
                # Handle exceptions (you can customize this as needed)
                print(f"Error processing Message ID: {message.get('MessageId')}. Error: {str(e)}")
                raise AirflowException(f"Failed to process message {message.get('MessageId')}") from e

    # Define task dependencies
    wait_for_sqs_message >> process_and_send_to_webhook(wait_for_sqs_message.output)
