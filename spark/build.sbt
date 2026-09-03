name := "presslake-spark"
version := "0.1.0"
scalaVersion := "2.12.18"

val sparkV = "3.5.5"

libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-sql" % sparkV % "provided",
  "org.apache.spark" %% "spark-sql" % sparkV % Test,
  "org.scalatest" %% "scalatest" % "3.2.19" % Test
)

ThisBuild / evictionErrorLevel := Level.Warn

assembly / assemblyJarName := "presslake-spark.jar"
assembly / assemblyMergeStrategy := {
  case PathList("META-INF", xs @ _*) =>
    xs.map(_.toLowerCase) match {
      case "services" :: _ => MergeStrategy.filterDistinctLines
      case _               => MergeStrategy.discard
    }
  case "reference.conf" => MergeStrategy.concat
  case _                => MergeStrategy.first
}

Test / parallelExecution := false
Test / fork := true
Test / javaOptions ++= Seq(
  "-Dspark.ui.enabled=false",
  "-Dspark.sql.shuffle.partitions=2",
  "-Xmx1g"
)
