package RunIsar

import de.unruh.isabelle.control.{IsabelleMLException}

/**
 * A wrapper exception class for IsabelleMLException that belongs to the RunIsar package.
 * This allows for better exception handling and encapsulation of Isabelle-specific exceptions.
 */
class RunIsarMLException(message: String, cause: Throwable = null) extends Exception(message, cause) {
  def this(original: IsabelleMLException) = this(original.getMessage, original)
}