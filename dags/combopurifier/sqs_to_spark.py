import jinja2
import yaml
import json
import logging
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone
from airflow.decorators import task, dag
from airflow.providers.amazon.aws.sensors.sqs import SqsSensor
from airflow.providers.amazon.aws.operators.sqs import SqsPublishOperator
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

# Initialize logger
logger = logging.getLogger(__name__)

# DAG configuration
default_args = {
    'owner': 'leonardo@cloudificando.com',
    'depends_on_past': False,
    'email': ['leonardo@cloudificando.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=5),
}

SQS_CONSUMER_CONNECTION_ID = 'sqs-connection-combopretifier'
SQS_PUBLISHER_CONNECTION_ID = 'sqs-publisher-combopurifier'
SQS_QUEUE_URL = 'https://sqs.us-east-2.amazonaws.com/068064050187/input-notification'
SQS_DLQ_QUEUE_URL = 'https://sqs.us-east-2.amazonaws.com/068064050187/input-notification-dlq'
TEMPLATE_PATH = "/opt/airflow/dags/repo/spark-jobs/combopurifier/combopurifier_spark.yaml"

@dag(
    dag_id='sqs_s3_to_spark',
    default_args=default_args,
    description='Retrieve messages from SQS and send to Spark K8s for processing files',
    schedule_interval=timedelta(seconds=35),
    start_date=datetime(2024, 4, 1),
    catchup=False,
    tags=['combopurifier', 'sqs', 'webhook', 'spark', 'minio', 'kubernetes', 's3'],
    max_active_runs=1,
    render_template_as_native_obj=True
)
def init():
    @task
    def render_template(**context):
        messages = context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages') or []
        message = messages[0]
        body = json.loads(message['Body'])
        object_key = unquote(body['Records'][0]['s3']['object']['key'])
        logger.info(f"Extracted file_input_key: {object_key}")
        unique_id = f"{context['dag'].dag_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{object_key.replace('/', '_').replace('.', '_')}"
        logger.info(f"Generated unique id: {unique_id}")
        with open(TEMPLATE_PATH) as file:
            rendered_yaml = jinja2.Template(file.read()).render(file_input_key=object_key, id=unique_id)
        return yaml.safe_load(rendered_yaml)


    @task(trigger_rule=TriggerRule.ONE_FAILED)
    def render_dlq_payload(**context):
        dag_id = context['dag'].dag_id
        execution_date = context['execution_date'].isoformat()
        task_instances = context['ti'].get_dagrun().get_task_instances()
        failed_tasks = [
            {
                'task_id': ti.task_id,
                'state': ti.state,
                'try_number': ti.try_number,
                'log_url': ti.log_url,
                'execution_date': ti.execution_date.isoformat(),
                'start_date': ti.start_date.isoformat() if ti.start_date else None,
                'end_date': ti.end_date.isoformat() if ti.end_date else None,
                'duration': ti.duration,
            }
            for ti in task_instances if ti.state == 'failed'
        ]
        original_messages = context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages') or []
        message_payload = {
            'dag_id': dag_id,
            'execution_date': execution_date,
            'failed_tasks': failed_tasks,
            'sqs_messages': original_messages,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(message_payload)

    start = EmptyOperator(task_id="start")

    wait_for_sqs_message = SqsSensor(
        task_id='wait_for_sqs_message',
        aws_conn_id=SQS_CONSUMER_CONNECTION_ID,
        sqs_queue=SQS_QUEUE_URL,
        max_messages=1,
        num_batches=1,
        wait_time_seconds=20,
        poke_interval=30,
        timeout=timedelta(days=7),
        mode='poke',
        visibility_timeout=30,
        delete_message_on_reception=True,
        deferrable=True,
    )

    render_yaml = render_template()

    combopurifier_spark = SparkKubernetesOperator(
        task_id='combopurifier_spark',
        namespace='spark-jobs',
        template_spec="{{ task_instance.xcom_pull(task_ids='render_template') }}",
        kubernetes_conn_id='kubernetes_in_cluster',
        do_xcom_push=False,
    )

    end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.ALL_DONE)

    failure_payload = render_dlq_payload()

    send_to_dlq = SqsPublishOperator(
        task_id='send_to_dlq',
        aws_conn_id=SQS_PUBLISHER_CONNECTION_ID,
        sqs_queue=SQS_DLQ_QUEUE_URL,
        message_content="{{ task_instance.xcom_pull(task_ids='render_dlq_payload') }}",
        message_attributes={},  # Add any necessary message attributes here
        delay_seconds=0,
        message_group_id=None,  # Set if using FIFO queues
    )

    # Define task dependencies
    start >> wait_for_sqs_message >> render_yaml >> combopurifier_spark >> end
    [wait_for_sqs_message, render_yaml, combopurifier_spark] >> failure_payload >> send_to_dlq

dag = init()
