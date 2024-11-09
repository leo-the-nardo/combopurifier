from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, broadcast
from spark_session import execute_spark

def spark_job(spark: SparkSession, params, *args, **kwargs):
    # Extract parameters
    s3_input_combo_path = params.get("source_bucket")
    s3_brazilian_words_path = params.get("brazilian_words_bucket")
    s3_output_path = params.get("output_bucket")
    s3_master_combo_path = params.get("master_bucket")
    # Load and broadcast the words table
    words_df = spark.read.text(s3_brazilian_words_path).select(lower("value").alias("word"))
    broadcasted_words_df = broadcast(words_df)
    broadcasted_words_df.createOrReplaceTempView("words")

    # Register paths as SQL variables
    spark.sql(f"""
        CREATE OR REPLACE TEMP VIEW bronze_table AS
        SELECT *
        FROM delta.`{s3_input_combo_path}`
    """)

    spark.sql("""
        CREATE OR REPLACE TEMP VIEW emails AS
        SELECT DISTINCT LOWER(email_tel) AS email_lower, email_tel
        FROM bronze_table
    """)

    # Use SQL with broadcast applied to words
    spark.sql("""
        CREATE OR REPLACE TEMP VIEW matching_emails AS
        SELECT DISTINCT e.email_tel
        FROM emails e
        JOIN words w ON e.email_lower LIKE CONCAT('%', w.word, '%')
    """)

    # Write to silver delta table as a .txt file with original emails
    matching_emails_df = spark.sql("SELECT email_tel FROM matching_emails")
    matching_emails_df.write.mode("overwrite").text(s3_output_path)

    # Check if the master path exists, create if it doesn't
    try:
        spark.read.format("delta").load(s3_master_combo_path)
    except Exception as e:
        # If the path does not exist, create an empty Delta table
        empty_df = spark.createDataFrame([], schema="email_tel STRING")
        empty_df.write.format("delta").save(s3_master_combo_path)
    # Append the matching emails to the master delta table
    spark.sql(f"""
        INSERT INTO delta.`{s3_master_combo_path}`
        SELECT email_tel
        FROM matching_emails
    """)

if __name__ == "__main__":
    execute_spark(method=spark_job)
