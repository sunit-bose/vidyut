// Intentionally violates Google Java Style for testing Checkstyle

package com.example; // Standard package statement

import java.util.List; // Unused import (if List is not used)
import java.util.ArrayList; // Used import

// Class name should start with an uppercase letter and be CamelCase.
// Let's make one that might violate a naming convention if rules are strict, e.g. too short or unusual.
// For Google checks, "incorrectClassName" would be a clear violation.
public class incorrectClassName { // Violation: Name 'incorrectClassName' must match pattern '^[A-Z][a-zA-Z0-9]*$'.

    // Field name should be lowerCamelCase.
    public int PublicField = 10; // Violation: Name 'PublicField' must match pattern '^[a-z][a-zA-Z0-9]*$'. Also, public non-final field.

    private int my_value; // Violation: Name 'my_value' must match pattern '^[a-z][a-zA-Z0-9]*$'. (snake_case)

    // Method name should be lowerCamelCase.
    public void MyMethod() { // Violation: Name 'MyMethod' must match pattern '^[a-z][a-zA-Z0-9]*$'.
        // Missing Javadoc for a public method
        int A = 5 + 3; // Violation: Local variable 'A' must match pattern '^[a-z][a-zA-Z0-9]*$'. Space around '+' is usually fine.
        System.out.println("This line is deliberately made very very very very very very very very very very very very very very very very very long to exceed the line length limit."); // Violation: Line is longer than X characters.

        if (A > 0) { // Missing space after 'if' if a rule enforces it. (Google style usually has space)
            System.out.println("Positive");
        } // Curly brace placement might be checked.

        // Magic number
        int magicNumber = 123; // Violation: '123' is a magic number.
    }

    // Parameter name should be lowerCamelCase
    public void anotherMethod(String BadName) { // Violation: Parameter 'BadName' must match pattern '^[a-z][a-zA-Z0-9]*$'.
         // Missing Javadoc
    }

    // Unused private method
    private void unUsedPrivateMethod() { // Violation: Unused private method 'unUsedPrivateMethod'.
        // This might be caught by PMD more often than Checkstyle, but some Checkstyle configs catch it.
    }
}

// Another class in the same file (generally discouraged, Checkstyle might flag this)
// class another_class_in_same_file {} // Violation: Name 'another_class_in_same_file' must match pattern '^[A-Z][a-zA-Z0-9]*$'.
                                   // And "Top level type another_class_in_same_file should be in its own file."
