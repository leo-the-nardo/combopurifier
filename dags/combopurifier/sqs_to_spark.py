import os
import jinja2
import yaml
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone
from airflow.decorators import task,dag
from airflow.providers.amazon.aws.sensors.sqs import SqsSensor
from airflow.operators.empty import EmptyOperator
import json
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.providers.cncf.kubernetes.sensors.spark_kubernetes import SparkKubernetesSensor

# Default arguments for the DAG
default_args = {
    'owner': 'leonardo@cloudificando.com',
    'depends_on_past': False,
    'email': ['leonardo@cloudificando.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=5),
}

SQS_CONNECTION_ID = 'sqs-connection-combopretifier'  # Ensure this matches your Airflow connection
SQS_QUEUE_URL = 'https://sqs.us-east-2.amazonaws.com/068064050187/input-notification'  # Replace with your SQS queue URL
TEMPLATE_PATH = "./combopurifier_spark.yaml"
# Define the DAG
@dag(
    dag_id='sqs_s3_to_spark',
    default_args=default_args,
    description='A DAG that retrieves messages from SQS and sends to spark k8s process files',
    schedule_interval=timedelta(seconds=35),
    start_date=datetime(2024, 4, 1),
    catchup=False,
    tags=['combopurifier', 'sqs', 'webhook', 'spark', 'minio', 'kubernetes', 's3'],
    max_active_runs=1,
)
def init():
    start = EmptyOperator(task_id="start")

    # SQS Sensor Task
    wait_for_sqs_message = SqsSensor(
        task_id='wait_for_sqs_message',
        aws_conn_id=SQS_CONNECTION_ID,
        sqs_queue=SQS_QUEUE_URL,
        max_messages=1,              # Maximum number of messages to retrieve per batch (up to 10)
        num_batches=1,                # Number of batches to retrieve per poke
        wait_time_seconds=20,         # Long polling duration (seconds)
        poke_interval=30,             # How often to poke the queue (seconds)
        timeout=timedelta(days=7),                  # Timeout for the sensor (seconds)
        mode='poke',                  # 'poke' or 'reschedule'
        visibility_timeout=30,        # Visibility timeout for messages
        delete_message_on_reception=True,  # Ensure messages are deleted upon retrieval
        deferrable=True,              # Allow deferring the task
    )
    @task
    def parse_sqs_input_filepath(**context):
        """
        Task to process SQS messages and extract the file_input_key.
        """
        messages = context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages')
        if not messages:
            print("No messages to process.")
            return None

        print(f"Processing messages: {messages}")

        try:
            # Extract the first message
            message = messages[0]
            body = json.loads(message['Body'])
            records = body.get('Records', [])
            if not records:
                print("No records found in message body.")
                return None

            # Extract the object key from the first record
            object_key_encoded = records[0]['s3']['object']['key']
            # Decode URL-encoded key if necessary
            file_input_key = unquote(object_key_encoded)
            print(f"Extracted file_input_key: {file_input_key}")

            # Push the file_input_key to XCom
            return file_input_key

        except (KeyError, json.JSONDecodeError) as e:
            print(f"Error parsing message: {e}")
            return None

    @task
    def generate_unique_id(file_input_key, **context):
        """
        Generate a unique ID using DAG ID, current datetime, and sanitized file_input_key.
        """
        if not file_input_key:
            raise ValueError("file_input_key is None or empty.")

        dag_id = context['dag'].dag_id
        # Use timezone-aware datetime in UTC
        current_time = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        # Replace "/" and "." in file_input_key with "_"
        sanitized_file_input_key = file_input_key.replace("/", "_").replace(".", "_")
        unique_id = f"{dag_id}-{current_time}-{sanitized_file_input_key}"
        print(f"Generated unique id: {unique_id}")
        return unique_id
    parse_task = parse_sqs_input_filepath()

    generate_id_task = generate_unique_id(parse_task)

    @task
    def render_template_spec(file_input_key, unique_id, **context):
        """
        Renders the SparkApplication spec using the Jinja template and returns it as a dictionary.
        """
        dag_id = context['dag'].dag_id

        if not file_input_key or not unique_id:
            raise ValueError("file_input_key or unique_id is missing.")

        # Load the Jinja template
        with open(TEMPLATE_PATH, 'r') as file:
            template_content = file.read()

        template = jinja2.Template(template_content)
        rendered_yaml = template.render(file_input_key=file_input_key, id=unique_id)
        print(f"Rendered SparkApplication YAML:\n{rendered_yaml}")

        # Convert YAML to Python dictionary
        spark_app_spec = yaml.safe_load(rendered_yaml)
        return spark_app_spec

    render_spec_task = render_template_spec(parse_task, generate_id_task)

    combopurifier_spark = SparkKubernetesOperator(
        task_id='combopurifier_spark',
        namespace='spark-jobs',
        # application_file='combopurifier_spark.yaml',  # Path to your SparkApplication YAML
        template_spec="{{ task_instance.xcom_pull(task_ids='render_template_spec') }}",
        kubernetes_conn_id='kubernetes_in_cluster',
        do_xcom_push=True,
        # env_from={
        #     'SPARK_SOURCE_BUCKET': "s3a://landing/{{ ti.xcom_pull(task_ids='parse_sqs_input_filepath', key='return_value') }}",
        #     'SPARK_TARGET_BUCKET': "s3a://lakehouse/bronze/combos/job-combopurifier-{{ ti.xcom_pull(task_ids='generate_unique_id', key='return_value') }}",
        #     # Static variables are already set in YAML; no need to override unless desired
        #     # 'SPARK_JOB_NAME': 'combopurifier-job',  # Already set in YAML
        #     # 'SPARK_MASTER_BUCKET': 's3a://lakehouse/silver/combos/master'  # Already set in YAML
        # },
        # env_vars=
        # Pass additional arguments if necessary
        # For example, you can add extra environment variables or configurations here
    )

    # Spark Kubernetes Sensor Task
    monitor_users = SparkKubernetesSensor(
        task_id='monitor_users',
        namespace='spark-jobs',
        application_name="{{ task_instance.xcom_pull(task_ids='combopurifier_spark')['metadata']['name'] }}",
        kubernetes_conn_id='kubernetes_in_cluster',
    )


    end = EmptyOperator(task_id="end")

    # Define task dependencies
    start >> wait_for_sqs_message >> parse_task >> generate_id_task >> render_spec_task >> combopurifier_spark >> monitor_users >> end
dag = init()