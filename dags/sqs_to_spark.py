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
    'email': ['leonardo@cloudificando.com'],
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
    schedule_interval=None,
    start_date=datetime(2024, 4, 1),
    catchup=False,
    tags=['example', 'sqs', 'webhook', 'taskflow'],
    max_active_runs=1
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
    def process_spark(**context):
        """
        Task to process SQS messages and send them to a webhook via HTTP POST.
        """
        messages = context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages')
        if not messages:
            print("No messages to process.")
            return
        print(f"Processing messages: {messages}")

    # Define task dependencies
    wait_for_sqs_message >> process_spark()
