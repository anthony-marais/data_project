package presslake

import java.nio.charset.StandardCharsets
import java.nio.file.Files

import org.apache.spark.sql.SparkSession
import org.scalatest.BeforeAndAfterAll
import org.scalatest.funsuite.AnyFunSuite

class SilverToParquetSpec extends AnyFunSuite with BeforeAndAfterAll {

  private var spark: SparkSession = _

  override def beforeAll(): Unit = {
    spark = SparkSession
      .builder()
      .master("local[2]")
      .appName("presslake-spark-test")
      .config("spark.ui.enabled", "false")
      .config("spark.sql.shuffle.partitions", "2")
      .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
  }

  override def afterAll(): Unit = {
    if (spark != null) spark.stop()
  }

  test("silver JSON hive-partitionné → parquet gold") {
    val root = Files.createTempDirectory("presslake-spark-")
    val silverDir =
      root.resolve("silver").resolve("source=france24").resolve("dt=2026-08-31")
    Files.createDirectories(silverDir)
    val json =
      """{
        |  "schema_version": 1,
        |  "feed_id": "france24",
        |  "content_hash": "fb78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3",
        |  "title": "Exemple silver PressLake",
        |  "canonical_url": "https://www.france24.com/fr/example-article",
        |  "author": "France 24",
        |  "published": "Mon, 31 Aug 2026 10:00:00 GMT",
        |  "parsed_at": "2026-08-31T12:05:00+00:00",
        |  "text": "Texte lisible extrait par trafilatura.",
        |  "text_source": "rss_summary",
        |  "bronze_s3_uri": "s3://presslake/bronze/source=france24/dt=2026-08-31/fb78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3.json",
        |  "feed_lang": "fr",
        |  "content_lang": "fr",
        |  "content_lang_confidence": 0.99
        |}""".stripMargin
    val bytes = json.getBytes(StandardCharsets.UTF_8)
    Files.write(
      silverDir.resolve(
        "fb78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3.json"
      ),
      bytes
    )
    val json2 = json.replace(
      "fb78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3",
      "aa78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3"
    )
    Files.write(
      silverDir.resolve(
        "aa78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3.json"
      ),
      json2.getBytes(StandardCharsets.UTF_8)
    )

    val input = root.resolve("silver").toAbsolutePath.toString
    val output = root.resolve("gold").toAbsolutePath.toString
    val n = SilverToParquet.convert(spark, input, output)
    assert(n === 2L)

    val back = spark.read.parquet(output)
    assert(back.count() === 2L)
    val hashes = back.collect().map(_.getAs[String]("content_hash")).toSet
    assert(hashes.size === 2)
    assert(hashes.contains("fb78ed72468c45b3895375890d347f6cf7c19e1f9ebe81578325efa95e362aa3"))
    val row = back.collect().head
    assert(row.getAs[String]("feed_id") === "france24")
    assert(row.getAs[String]("dt") === "2026-08-31")
    assert(row.getAs[String]("text").contains("trafilatura"))
  }
}
