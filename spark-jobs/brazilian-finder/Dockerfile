# Use the base image
FROM  cloudificando/spark-py-s3a-delta:3.5.3

# Copy your PySpark scripts into the container
COPY brazilian-finder_spark.py /opt/spark/scripts/job.py
COPY ../spark_session.py /opt/spark/scripts/
#docker build -t leothenardo/spark-brazilian-finder:1.0.0 ./spark-jobs/brazilian-finder/
#docker push leothenardo/spark-brazilian-finder:1.0.0