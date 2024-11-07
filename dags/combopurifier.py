import jinja2
import yaml
import json
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone
from airflow.decorators import task, dag
from airflow.providers.amazon.aws.sensors.sqs import SqsSensor
from airflow.providers.amazon.aws.operators.sqs import SqsPublishOperator
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

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
    dag_id='combopurifier-dag',
    default_args=default_args,
    description='Retrieve messages from SQS and send to Spark K8s for processing files',
    schedule_interval=timedelta(seconds=35),
    start_date=datetime(2024, 4, 1),
    catchup=False,
    tags=['combopurifier', 'sqs', 'webhook', 'spark', 'minio', 'kubernetes', 's3'],
    max_active_runs=1,
    user_defined_filters={
        'fromjson': lambda s: json.loads(s),
        'tojson': lambda x: json.dumps(x)
    },
    render_template_as_native_obj=False
)
def init():
    @task
    def render_template(**context):
        messages = context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages') or []
        object_key = unquote(json.loads(messages[0]['Body'])['Records'][0]['s3']['object']['key'])
        unique_id = f"{context['dag'].dag_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{object_key.replace('/', '_').replace('.', '_')}"
        with open(TEMPLATE_PATH) as file:
            rendered_yaml = jinja2.Template(file.read()).render(file_input_key=object_key, id=unique_id)
        return json.dumps(yaml.safe_load(rendered_yaml))

    @task(trigger_rule=TriggerRule.ONE_FAILED)
    def render_dlq_payload(**context):
        task_instances = context['ti'].get_dagrun().get_task_instances()
        failed_tasks = [
            {
                'task_id': ti.task_id,
                'state': ti.state,
                'try_number': ti.try_number,
                'log_url': ti.log_url,
                'duration': ti.duration,
            }
            for ti in task_instances if ti.state == 'failed'
        ]
        message_payload = {
            'dag_id': context['dag'].dag_id,
            'run_id': context['run_id'],
            'execution_date': context['execution_date'].isoformat(),
            'failed_tasks': failed_tasks,
            'original_messages': context['ti'].xcom_pull(task_ids='wait_for_sqs_message', key='messages') or [],
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        return message_payload

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
        template_spec="{{ task_instance.xcom_pull(task_ids='render_template') | fromjson }}", # i need this as dict
        kubernetes_conn_id='kubernetes_in_cluster',
        do_xcom_push=False,
    )

    end = EmptyOperator(task_id="end")

    failure_payload = render_dlq_payload()

    send_to_dlq = SqsPublishOperator(
        task_id='send_to_dlq',
        aws_conn_id=SQS_PUBLISHER_CONNECTION_ID,
        sqs_queue=SQS_DLQ_QUEUE_URL,
        message_content="{{ task_instance.xcom_pull(task_ids='render_dlq_payload') | tojson }}", # i need this as string
        message_attributes={},
        delay_seconds=0,
        message_group_id=None,
    )

    start >> wait_for_sqs_message >> render_yaml >> combopurifier_spark >> end
    [wait_for_sqs_message, render_yaml, combopurifier_spark] >> failure_payload >> send_to_dlq

dag = init()
