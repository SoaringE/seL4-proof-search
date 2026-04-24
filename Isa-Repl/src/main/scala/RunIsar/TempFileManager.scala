package RunIsar

import java.nio.file.{Files, Paths, StandardCopyOption, FileSystem, FileSystems}
import scala.jdk.CollectionConverters._
import java.io.{File, IOException}
import java.net.URI
import scala.util.Using
import scala.collection.mutable.Set

/**
 * Manages temporary file operations including copying resources from JAR/filesystem.
 * Handles both development and packaged JAR environments.
 */
class TempFileManager {
  private val tempDirs = Set[File]()

  // Add shutdown hook for cleanup
  Runtime.getRuntime.addShutdownHook(new Thread {
    override def run(): Unit = {
      cleanupAll()
    }
  })

  /**
   * Clean up all temporary directories
   */
  def cleanupAll(): Unit = {
    tempDirs.foreach { dir =>
      try {
        if (dir.exists()) {
          Files.walk(dir.toPath)
            .sorted(java.util.Comparator.reverseOrder())
            .forEach { path =>
              try {
                Files.deleteIfExists(path)
              } catch {
                case e: IOException => 
                  println(s"Warning: Could not delete ${path}: ${e.getMessage}")
              }
            }
        }
      } catch {
        case e: Exception => 
          println(s"Error cleaning up ${dir}: ${e.getMessage}")
      }
    }
    tempDirs.clear()
  }

  /**
   * Clean up a specific temporary directory
   */
  def cleanup(dir: File): Unit = {
    try {
      if (dir.exists()) {
        Files.walk(dir.toPath)
          .sorted(java.util.Comparator.reverseOrder())
          .forEach { path =>
            try {
              Files.deleteIfExists(path)
            } catch {
              case e: IOException => 
                println(s"Warning: Could not delete ${path}: ${e.getMessage}")
            }
          }
      }
      tempDirs -= dir
    } catch {
      case e: Exception => 
        println(s"Error cleaning up ${dir}: ${e.getMessage}")
    }
  }

  /**
   * Copies a resource directory to target location.
   * @param sourcePath Resource path relative to classloader (e.g., "some/dir")
   * @param targetDir Destination directory
   * @throws IOException If resource not found or copy fails
   */
  def copyResources(sourcePath: String, targetDir: File): Unit = {
    require(sourcePath != null && targetDir != null, "Parameters cannot be null")

    val resourceUrl = Option(getClass.getClassLoader.getResource(sourcePath))
      .getOrElse(throw new IOException(s"Resource not found: $sourcePath"))

    val uri = resourceUrl.toURI

    // Ensure target directory exists
    Files.createDirectories(targetDir.toPath)

    uri.getScheme match {
      case "jar" => copyFromJar(uri, sourcePath, targetDir)
      case "file" => copyFromFileSystem(uri, targetDir)
      case other => throw new IOException(s"Unsupported URI scheme: $other")
    }
  }

  /** Copies resources from within a JAR file */
  private def copyFromJar(jarUri: URI, sourcePath: String, targetDir: File): Unit = {
    var jarFs: FileSystem = null
    try {
      jarFs = FileSystems.newFileSystem(jarUri, new java.util.HashMap[String, Any])
      val jarPath = jarUri.toString.split("!")(1).stripPrefix("/")
      val rootPath = jarFs.getPath(jarPath)

      Files.walk(rootPath).forEach { sourceFile =>
        if (!Files.isDirectory(sourceFile)) {
          val relativePath = rootPath.relativize(sourceFile).toString
          val targetFile = targetDir.toPath.resolve(relativePath)
          Files.createDirectories(targetFile.getParent)
          Files.copy(sourceFile, targetFile, StandardCopyOption.REPLACE_EXISTING)
          // println(s"Copied: $sourceFile -> $targetFile")
        }
      }
    } finally {
      if (jarFs != null) jarFs.close()
    }
  }

  /** Copies resources from regular filesystem */
  private def copyFromFileSystem(uri: URI, targetDir: File): Unit = {
    val sourceDir = Paths.get(uri)
    Files.walk(sourceDir).forEach { sourceFile =>
      if (!Files.isDirectory(sourceFile)) {
        val relativePath = sourceDir.relativize(sourceFile).toString
        val targetFile = targetDir.toPath.resolve(relativePath)
        Files.createDirectories(targetFile.getParent)
        Files.copy(sourceFile, targetFile, StandardCopyOption.REPLACE_EXISTING)
        // println(s"Copied: $sourceFile -> $targetFile")
      }
    }
  }

  /**
   * Creates a temporary directory that auto-deletes on JVM exit
   * @param prefix Directory name prefix
   * @return Created directory
   */
  def createTempDir(prefix: String): File = {
    val dir = Files.createTempDirectory(prefix).toFile
    tempDirs += dir
    dir.deleteOnExit()
    
    Files.walk(dir.toPath)
      .forEach(_.toFile.deleteOnExit())

    // println(s"Created temp directory: ${dir.getAbsolutePath}")
    dir
  }
}

object TempFileManager {
  private val instance = new TempFileManager()

  def createTempDir(prefix: String): File = {
    instance.createTempDir(prefix)
  }

  def copyResources(resourcePath: String, targetDir: File): Unit = {
    instance.copyResources(resourcePath, targetDir)
  }

  def cleanupAll(): Unit = {
    instance.cleanupAll()
  }

  def cleanup(dir: File): Unit = {
    instance.cleanup(dir)
  }
}