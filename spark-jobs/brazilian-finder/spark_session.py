import os
from sys import argv
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf

def execute_spark(method, configs=None):
    conf = SparkConf()
    if configs is not None:
        conf.setAll(configs)

    spark_env_vars = {
        key.replace('SPARK_', '').lower(): value
        for key, value in os.environ.items() if key.startswith('SPARK_')
    }

    parameters = {}
    if len(argv) > 1:
        for argument in argv[1:]:
            if '=' in argument:
                key, value = argument.split('=', 1)
                parameters[key.lower()] = value
            else:
                pass

    merged_params = {**spark_env_vars, **parameters}

    app_name = merged_params.get("job_name", "SparkApplication")
    spark = SparkSession.builder \
        .appName(app_name) \
        .config(conf=conf) \
        .getOrCreate()

    try:
        method(spark=spark, params=merged_params)
    finally:
        spark.stop()
