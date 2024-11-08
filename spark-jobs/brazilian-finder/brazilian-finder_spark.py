from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, broadcast
from spark_session import execute_spark

def spark_job(spark: SparkSession, params, *args, **kwargs):
    # Extract parameters
    s3_input_combo_path = params.get("source_bucket")
    s3_brazilian_words_path = params.get("brazilian_words_bucket")
    s3_output_path = params.get("output_bucket")
    s3_master_combo_path = params.get("master_bucket")

    # Register paths as variables for SQL
    spark.sql(f"""
        CREATE OR REPLACE TEMP VIEW bronze_table AS
        SELECT *
        FROM delta.`{s3_input_combo_path}`
    """)

    spark.sql(f"""
        CREATE OR REPLACE TEMP VIEW words AS
        SELECT LOWER(value) AS word
        FROM text.`{s3_brazilian_words_path}`
    """)

    spark.sql("""
        CREATE OR REPLACE TEMP VIEW emails AS
        SELECT DISTINCT LOWER(email_tel) AS email_lower, email_tel
        FROM bronze_table
    """)

    spark.sql("""
        CREATE OR REPLACE TEMP VIEW matching_emails AS
        SELECT DISTINCT e.email_tel
        FROM emails e
        JOIN /*+ BROADCAST(w) */ words w
          ON e.email_lower LIKE CONCAT('%', w.word, '%')
    """)

    # Write to silver delta table as a .txt file with original emails
    spark.sql(f"""
        INSERT OVERWRITE TEXT.`{s3_output_path}`
        SELECT email_tel
        FROM matching_emails
    """)

    # Append the matching emails to the master delta table
    spark.sql(f"""
        INSERT INTO delta.`{s3_master_combo_path}`
        SELECT email_tel
        FROM matching_emails
    """)
if __name__ == "__main__":
    execute_spark(method=spark_job)
