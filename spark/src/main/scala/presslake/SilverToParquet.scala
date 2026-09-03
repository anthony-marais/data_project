package presslake

import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

/** Backfill volume : silver JSON (MinIO) → gold parquet. Pas le poll RSS. */
object SilverToParquet {

  def main(args: Array[String]): Unit = {
    val input = argValue(args, "--input").getOrElse("s3a://presslake/silver")
    val output =
      argValue(args, "--output").getOrElse("s3a://presslake/gold/layer=silver_parquet")

    val spark = SparkSession
      .builder()
      .appName("presslake-silver-to-parquet")
      .getOrCreate()

    try {
      val n = convert(spark, input, output)
      Console.err.println(s"presslake spark : $n ligne(s) → $output")
    } finally {
      spark.stop()
    }
  }

  def convert(spark: SparkSession, input: String, output: String): Long = {
    import spark.implicits._

    // Un objet JSON pretty-print par fichier. spark.read.json(multiLine) passe par
    // CombineFileInputFormat / BinaryFileRDD : N fichiers → 1 split → 0 ligne.
    // binaryFile = une ligne par fichier, puis from_json sur le texte entier.
    val files = spark.read
      .format("binaryFile")
      .option("recursiveFileLookup", "true")
      .option("pathGlobFilter", "*.json")
      .load(input)

    val withRaw = files.select(
      col("content").cast("string").as("json_str"),
      col("path")
    ).filter(col("json_str").isNotNull && length(trim(col("json_str"))) > 0)

    val schema =
      spark.read.option("mode", "PERMISSIVE").json(withRaw.select("json_str").as[String]).schema

    var df = withRaw
      .select(
        from_json(col("json_str"), schema).as("doc"),
        regexp_extract(col("path"), "dt=([^/]+)", 1).as("dt_path"),
        regexp_extract(col("path"), "source=([^/]+)", 1).as("source_path")
      )
      .select(col("doc.*"), col("dt_path"), col("source_path"))

    df = if (df.columns.contains("dt")) {
      df.withColumn("dt", coalesce(col("dt").cast("string"), col("dt_path")))
        .drop("dt_path")
    } else {
      df.withColumn("dt", col("dt_path")).drop("dt_path")
    }

    if (!df.columns.contains("feed_id")) {
      df = df.withColumn("feed_id", col("source_path"))
    }
    if (df.columns.contains("_corrupt_record")) {
      df = df.drop("_corrupt_record")
    }

    val out = df
      .drop("source_path", "source")
      .filter(col("content_hash").isNotNull)
      .filter(col("text").isNotNull && length(col("text")) > 0)
      .filter(col("feed_id").isNotNull)
      .filter(col("dt").isNotNull && col("dt") =!= "")

    val n = out.count()
    if (n == 0) {
      throw new IllegalStateException(
        s"Aucune ligne silver exploitable sous $input (presslake parse, JSON lisible)"
      )
    }

    out.write
      .mode("overwrite")
      .partitionBy("feed_id", "dt")
      .parquet(output)

    n
  }

  private def argValue(args: Array[String], flag: String): Option[String] = {
    val i = args.indexOf(flag)
    if (i >= 0 && i + 1 < args.length) Some(args(i + 1)) else None
  }
}
