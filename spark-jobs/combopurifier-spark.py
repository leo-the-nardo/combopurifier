# process_txt_file_sql.py

import sys
from pyspark.sql import SparkSession

def parse_s3_path(s3_path):
    """
    Parses an S3 URI into bucket and key.
    
    Args:
        s3_path (str): S3 URI (e.g., s3://bucket/key)
    
    Returns:
        tuple: (bucket, key)
    """
    if not s3_path.startswith("s3://"):
        raise ValueError("Invalid S3 path")
    s3_path = s3_path[5:]
    parts = s3_path.split('/', 1)
    if len(parts) != 2:
        raise ValueError("S3 path must include bucket and key")
    return parts[0], parts[1]

def main(txt_s3_path, output_txt_s3_path, master_delta_s3_path, master_delta_table_path):
    """
    Main function to process a single TXT file using Spark SQL.
    
    Args:
        txt_s3_path (str): S3 path to the TXT file.
        output_txt_s3_path (str): S3 path to write the cleaned TXT file.
        master_delta_s3_path (str): S3 path to the master Delta Lake dataset.
        master_delta_table_path (str): S3 path to the master Delta Lake table.
    """
    spark = SparkSession.builder \
        .appName("ProcessTxtFileSQL") \
        .getOrCreate()

    # Enable Delta Lake support
    spark.sparkContext.setLogLevel("WARN")
    spark.sql("SET spark.sql.legacy.timeParserPolicy=LEGACY")

    # Register Delta Lake
    spark.sparkContext._jvm.io.delta.tables.DeltaTable

    # Read the incoming TXT file
    df_incoming = spark.read.text(txt_s3_path)
    df_incoming.createOrReplaceTempView("incoming_data")

    # Define SQL query for regex extraction and filtering
    query_extraction = """
    SELECT 
        regexp_extract(value, '([^\\s]+@[^\\s]+:[^\\s]+)', 1) AS match
    FROM 
        incoming_data
    WHERE 
        trim(regexp_extract(value, '([^\\s]+@[^\\s]+:[^\\s]+)', 1)) != ''
    """

    df_extracted = spark.sql(query_extraction)
    df_extracted.createOrReplaceTempView("extracted_data")

    # Deduplicate the records
    query_dedup = """
    SELECT DISTINCT match
    FROM extracted_data
    """
    df_deduplicated = spark.sql(query_dedup)
    df_deduplicated.createOrReplaceTempView("deduplicated_data")

    # Read the master Delta Lake table
    df_master = spark.read.format("delta").load(master_delta_s3_path)
    df_master.createOrReplaceTempView("master_data")

    # Perform an anti-join to remove existing records
    query_cleaned = """
    SELECT 
        deduplicated_data.match
    FROM 
        deduplicated_data
    LEFT ANTI JOIN 
        master_data 
    ON 
        deduplicated_data.match = master_data.match
    """
    df_cleaned = spark.sql(query_cleaned)
    df_cleaned.createOrReplaceTempView("cleaned_data")

    # Write the cleaned data back to S3 as a TXT file
    query_write_txt = """
    SELECT match
    FROM cleaned_data
    """
    df_write_txt = spark.sql(query_write_txt)
    df_write_txt.write.mode("overwrite").text(output_txt_s3_path)

    # Append the cleaned data to the master Delta Lake table
    query_append_master = """
    SELECT match
    FROM cleaned_data
    """
    df_append_master = spark.sql(query_append_master)
    df_append_master.write.format("delta").mode("append").save(master_delta_table_path)

    spark.stop()

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: process_txt_file_sql.py <txt_s3_path> <output_txt_s3_path> <master_delta_s3_path> <master_delta_table_path>")
        sys.exit(-1)

    txt_s3_path = sys.argv[1]
    output_txt_s3_path = sys.argv[2]
    master_delta_s3_path = sys.argv[3]
    master_delta_table_path = sys.argv[4]

    main(txt_s3_path, output_txt_s3_path, master_delta_s3_path, master_delta_table_path)