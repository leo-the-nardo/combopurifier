from urllib.parse import quote
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower
from spark_session import execute_spark
import re

def spark_job(spark: SparkSession, params, *args, **kwargs):
    # Extract parameters
    s3_input_combo_path = quote(params.get("source_bucket"), safe=':/')
    s3_brazilian_words_path = quote(params.get("brazilian_words_bucket"), safe=':/')
    s3_output_path = quote(params.get("output_bucket"), safe=':/')
    s3_master_combo_path = quote(params.get("master_bucket"), safe=':/')

    # Load words and collect to a list
    words_df = spark.read.text(s3_brazilian_words_path).select(lower("value").alias("word"))
    words_list = [row.word for row in words_df.collect()]

    # Create regex pattern
    pattern = '|'.join([re.escape(word) for word in words_list])

    # Read emails and select necessary columns
    emails_df = spark.read.format('delta').load(s3_input_combo_path) \
        .select(lower(col('email_tel')).alias('email_lower'), 'email_tel').distinct()

    # Filter emails using rlike
    matching_emails_df = emails_df.filter(col('email_lower').rlike(pattern)) \
        .select('email_tel').distinct()

    # Write matching emails to output path
    matching_emails_df.write.mode("overwrite").text(s3_output_path)

    # Append matching emails to the master delta table
    matching_emails_df.write.format("delta").mode("append").save(s3_master_combo_path)

if __name__ == "__main__":
    execute_spark(method=spark_job)
