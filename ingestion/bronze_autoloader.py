# Databricks notebook source
# Auto Loader: landing volume (JSON lines) -> dev.bronze Delta tables.
# The first line above makes Databricks open this .py file as a notebook.

# COMMAND ----------

import os

from pyspark.sql import functions as F

CATALOG = "dev"
LANDING = f"/Volumes/{CATALOG}/bronze/landing"
CHECKPOINTS = f"/Volumes/{CATALOG}/bronze/checkpoints"

tables = ["customers", "sellers", "products", "orders",
          "order_items", "order_payments", "order_reviews", "fx_rates"]

# COMMAND ----------

queries = []
for t in tables:
    # Nothing has been exported for this table yet (fx_rates has no exporter so far)
    if not os.path.exists(f"{LANDING}/{t}"):
        print(f"Skipping {t}: no folder at {LANDING}/{t}")
        continue

    query = (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINTS}/{t}/_schema")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .load(f"{LANDING}/{t}/")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .writeStream
        .option("checkpointLocation", f"{CHECKPOINTS}/{t}")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .toTable(f"{CATALOG}.bronze.{t}"))
    queries.append(query)

# Wait for every table's batch to finish before the notebook ends
for query in queries:
    query.awaitTermination()
