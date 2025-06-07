package com.example;

import java.util.ArrayList;
import java.util.List;

/**
 * A simple class that adheres to Google Java Style for Checkstyle testing.
 */
public class CheckstyleClean {

    private static final int DEFAULT_CAPACITY = 10;
    private String message;
    private final List<String> items;

    /**
     * Constructs a CheckstyleClean object.
     * @param initialMessage the initial message.
     */
    public CheckstyleClean(String initialMessage) {
        this.message = initialMessage;
        this.items = new ArrayList<>(DEFAULT_CAPACITY);
    }

    /**
     * Gets the message.
     * @return the current message.
     */
    public String getMessage() {
        return message;
    }

    /**
     * Sets the message.
     * @param newMessage the new message to set.
     */
    public void setMessage(String newMessage) {
        this.message = newMessage;
    }

    /**
     * Adds an item to the list.
     * @param item the item to add.
     */
    public void addItem(String item) {
        if (item != null && !item.isEmpty()) {
            this.items.add(item);
        }
    }

    /**
     * Main method for demonstration.
     * @param args command-line arguments (not used).
     */
    public static void main(String[] args) {
        CheckstyleClean clean = new CheckstyleClean("Hello Checkstyle!");
        clean.addItem("Item 1");
        System.out.println(clean.getMessage());
        System.out.println("Items count: " + clean.items.size());
        System.out.println("Default capacity was: " + DEFAULT_CAPACITY);
    }
}
