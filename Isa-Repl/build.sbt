scalaVersion := "2.13.14"

lazy val root = (project in file("."))
  .settings(
    name := "Isa-Repl",
    organization := "ch.epfl.scala",
    version := "1.0",

    libraryDependencies ++= Seq(
      "org.scala-lang.modules" %% "scala-parser-combinators" % "2.1.1",
      "net.sf.py4j" % "py4j" % "0.10.9.7" exclude("org.slf4j", "*"),
      "ch.qos.logback" % "logback-classic" % "1.1.3",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test,
      "de.unruh" %% "scala-isabelle" % "0.4.3"
    ),

    resolvers ++= Resolver.sonatypeOssRepos("snapshots"),

    assembly / assemblyOutputPath := file("target/IsaREPL.jar"),
    assembly / mainClass := Some("org.isarepl.IsaReplGatewayServer"),
    assembly / assemblyMergeStrategy := {
      case PathList("META-INF", "MANIFEST.MF") => MergeStrategy.discard
      case PathList("META-INF", "services", _*) => MergeStrategy.filterDistinctLines
      case PathList("META-INF", _*) => MergeStrategy.discard
      case "reference.conf" => MergeStrategy.concat
      case _ => MergeStrategy.first
    }
  )