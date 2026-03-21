package com.hypixelai;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Simple config file for the HypixelAI mod.
 * Stored at .minecraft/config/hypixelai.properties
 */
public class HypixelAIConfig {

    private static String apiUrl = "http://localhost:5000/api/ask";
    private static String apiKey = "";
    private static Path configPath;

    public static void load() {
        try {
            // Find config directory
            Path configDir = Path.of("config");
            if (!Files.exists(configDir)) {
                Files.createDirectories(configDir);
            }

            configPath = configDir.resolve("hypixelai.properties");

            if (Files.exists(configPath)) {
                // Read existing config
                try (BufferedReader reader = Files.newBufferedReader(configPath, StandardCharsets.UTF_8)) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        line = line.trim();
                        if (line.startsWith("#") || !line.contains("=")) continue;

                        String[] parts = line.split("=", 2);
                        String key = parts[0].trim();
                        String value = parts.length > 1 ? parts[1].trim() : "";

                        switch (key) {
                            case "api_url" -> apiUrl = value;
                            case "api_key" -> apiKey = value;
                        }
                    }
                }
                HypixelAIMod.LOGGER.info("[HypixelAI] Config loaded from {}", configPath);
            } else {
                // Create default config
                save();
                HypixelAIMod.LOGGER.info("[HypixelAI] Default config created at {}", configPath);
            }

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to load config", e);
        }
    }

    private static void save() {
        try {
            String content = """
                    # HypixelAI Mod Configuration
                    #
                    # api_url: URL of your bot's API endpoint
                    # If the bot runs on the same PC, use localhost.
                    # If on another PC on your network, use that PC's IP.
                    api_url=%s

                    # api_key: Must match INGAME_API_KEY in your bot's .env file
                    # Leave blank if you didn't set one.
                    api_key=%s
                    """.formatted(apiUrl, apiKey);

            Files.writeString(configPath, content, StandardCharsets.UTF_8);
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to save config", e);
        }
    }

    public static String getApiUrl() {
        return apiUrl;
    }

    public static String getApiKey() {
        return apiKey;
    }

    public static String getConfigPath() {
        return configPath != null ? configPath.toString() : "config/hypixelai.properties";
    }
}
