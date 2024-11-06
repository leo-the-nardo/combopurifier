import os
from sys import argv
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf

def execute_spark(method, configs=None):
    """
    Initializes a SparkSession with the given configurations and executes the provided method.

    Parameters:
    - method: The Spark job function to execute.
    - configs: A list of tuples containing Spark configuration key-value pairs.
    """
    conf = SparkConf()

    if configs is not None:
        conf.setAll(configs)

    # 1. Collect Environment Variables Prefixed with "SPARK_"
    spark_env_vars = {
        key.replace('SPARK_', '').lower(): value
        for key, value in os.environ.items() if key.startswith('SPARK_')
    }

    # 2. Parse Command-Line Arguments Formatted as key=value
    parameters = {}
    if len(argv) > 1:
        for argument in argv[1:]:
            if '=' in argument:
                key, value = argument.split('=', 1)
                parameters[key.lower()] = value
            else:
                # Handle arguments without '=' if necessary
                pass  # You can log a warning or raise an exception

    # 3. Merge Environment Variables and Command-Line Arguments
    # Command-line arguments will override environment variables if keys collide
    merged_params = {**spark_env_vars, **parameters}

    # 4. Initialize SparkSession with App Name from Parameters
    app_name = merged_params.get("job_name", "SparkApplication")
    spark = SparkSession.builder \
        .appName(app_name) \
        .config(conf=conf) \
        .getOrCreate()

    try:
        # 5. Execute the Spark Job Method with SparkSession and Parameters
        method(spark=spark, params=merged_params)
    finally:
        # 6. Ensure SparkSession is Stopped After Job Completion
        spark.stop()
