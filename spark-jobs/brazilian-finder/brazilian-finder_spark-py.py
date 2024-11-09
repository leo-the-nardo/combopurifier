from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, broadcast
from spark_session import execute_spark

def spark_job(spark: SparkSession, params, *args, **kwargs):
    # Extract parameters
    s3_input_combo_path = params.get("source_bucket")
    s3_brazilian_words_path = params.get("brazilian_words_bucket")
    s3_output_path = params.get("matching_emails_output_path")
    s3_master_combo_path = params.get("master_bucket")

    # Read the bronze delta table
    df_bronze = spark.read.format("delta").load(s3_input_combo_path)

    # Read the Brazilian words and lowercase them for matching
    df_words = spark.read.text(s3_brazilian_words_path).toDF("word")
    df_words = df_words.select(lower(col("word")).alias("word"))

    # Prepare the emails: create a lowercase version for matching
    df_emails = df_bronze.select(
        lower(col("email_tel")).alias("email_lower"),  # Lowercased for matching
        "email_tel"  # Original email preserved
    ).distinct()

    # Broadcast the words DataFrame for efficient joining
    df_words_broadcast = broadcast(df_words)

    # Join emails with words where the lowercase email contains the lowercase word
    df_matching_emails = df_emails.join(
        df_words_broadcast,
        df_emails.email_lower.contains(df_words_broadcast.word),
        "inner"
    ).select("email_tel").distinct()  # Select original email

    # Write to silver delta table as a .txt file with original emails
    df_matching_emails.coalesce(1).write.mode("overwrite").text(s3_output_path)

    # Append the matching emails to the master delta table
    df_matching_emails.write.format("delta").mode("append").save(s3_master_combo_path)

if __name__ == "__main__":
    execute_spark(method=spark_job)
