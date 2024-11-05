import os
import shutil
from pyspark.sql import SparkSession
from pyspark.sql.functions import regexp_extract, col, trim

# Initialize Spark session
spark = SparkSession.builder.appName("PatternExtraction").getOrCreate()

# Load the file into a DataFrame
df = spark.read.text("/opt/bitnami/spark/jobs/input.txt")  # Path to your input file

# Define the regex pattern to match email-password pairs
pattern = r'([^\s]+@[^\s]+:[^\s]+)'

# Extract matches using regexp_extract
df_extracted = (
    df
    .select(regexp_extract(col("value"), pattern, 1).alias("match"))  # Extract the match using regex
    .filter(trim(col("match")) != "")  # Remove empty matches
)

# Show the extracted results
df_extracted.show(truncate=False)
# Write output to a temporary directory
# Specify the temporary output directory
temp_output_dir = "/opt/bitnami/spark/jobs/temp_output"

# Write the output to a temporary directory, using coalesce(1) to ensure a single file
df_extracted.coalesce(1).write.mode("overwrite").text(temp_output_dir)

# Move the output file to output.txt in the desired location
# Find the generated part file
output_file = os.path.join(temp_output_dir, "part-*")  # This will match the part file generated
output_txt_file = "/opt/bitnami/spark/jobs/output.txt"   # Desired output file name

# Use the shell command to move the part file to output.txt
os.system(f"mv {output_file} {output_txt_file}")

# Clean up: Remove the temporary output directory
shutil.rmtree(temp_output_dir)
