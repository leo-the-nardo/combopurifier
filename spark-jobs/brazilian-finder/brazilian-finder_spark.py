from urllib.parse import quote
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, lit, array
from spark_session import execute_spark
from functools import reduce

def spark_job(spark: SparkSession, params, *args, **kwargs):
    # Extract parameters
    s3_input_combo_path = quote(params.get("source_bucket"), safe=':/')
    s3_brazilian_words_path = quote(params.get("brazilian_words_bucket"), safe=':/')
    s3_output_path = quote(params.get("output_bucket"), safe=':/')
    s3_master_combo_path = quote(params.get("master_bucket"), safe=':/')

    # Load words and collect to a list
    words_df = spark.read.text(s3_brazilian_words_path).select(lower("value").alias("word"))
    words_list = [row.word for row in words_df.collect() if row.word]

    # Read emails and select necessary columns
    emails_df = spark.read.format('delta').load(s3_input_combo_path) \
        .select(lower(col('email_tel')).alias('email_lower'), 'email_tel')

    # Repartition to increase parallelism
    num_partitions = 100  # Adjust based on your cluster configuration
    emails_df = emails_df.repartition(num_partitions)

    # Create a combined condition using 'contains' and 'reduce'
    conditions = [col('email_lower').contains(word) for word in words_list]
    combined_condition = reduce(lambda x, y: x | y, conditions)

    # Filter emails using the combined condition
    matching_emails_df = emails_df.filter(combined_condition).select('email_tel').distinct()

    # Write matching emails to output path
    matching_emails_df.write.mode("overwrite").text(s3_output_path)

    # Append matching emails to the master delta table
    matching_emails_df.write.format("delta").mode("append").save(s3_master_combo_path)

if __name__ == "__main__":
    execute_spark(method=spark_job)
