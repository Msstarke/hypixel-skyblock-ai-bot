package com.hypixelai;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Config for the HypixelAI mod.
 * Stored at .minecraft/config/hypixelai.properties
 *
 * Stores license key and session token. Server URL is hardcoded.
 */
public class HypixelAIConfig {

    private static final String API_BASE = "https://sky-ai.uk";

    private static String licenseKey = "";
    private static String sessionToken = "";
    private static Path configPath;

    public static void load() {
        try {
            Path configDir = Path.of("config");
            if (!Files.exists(configDir)) {
                Files.createDirectories(configDir);
            }

            configPath = configDir.resolve("hypixelai.properties");

            if (Files.exists(configPath)) {
                try (BufferedReader reader = Files.newBufferedReader(configPath, StandardCharsets.UTF_8)) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        line = line.trim();
                        if (line.startsWith("#") || !line.contains("=")) continue;

                        String[] parts = line.split("=", 2);
                        String key = parts[0].trim();
                        String value = parts.length > 1 ? parts[1].trim() : "";

                        switch (key) {
                            case "license_key" -> licenseKey = value;
                            case "session_token" -> sessionToken = value;
                        }
                    }
                }
                HypixelAIMod.LOGGER.info("[HypixelAI] Config loaded from {}", configPath);
            } else {
                save();
                HypixelAIMod.LOGGER.info("[HypixelAI] Default config created at {}", configPath);
            }

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to load config", e);
        }
    }

    public static void save() {
        try {
            String content = """
                    # HypixelAI Mod Configuration
                    # Use !aikey <key> in-game to activate your license.
                    license_key=%s
                    session_token=%s
                    """.formatted(licenseKey, sessionToken);

            Files.writeString(configPath, content, StandardCharsets.UTF_8);
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to save config", e);
        }
    }

    public static String getApiUrl() {
        return API_BASE + "/api/ask";
    }

    public static String getActivateUrl() {
        return API_BASE + "/api/activate";
    }

    public static String getBaseUrl() {
        return API_BASE;
    }

    public static String getLicenseKey() {
        return licenseKey;
    }

    public static void setLicenseKey(String key) {
        licenseKey = key;
        save();
    }

    public static String getSessionToken() {
        return sessionToken;
    }

    public static void setSessionToken(String token) {
        sessionToken = token;
        save();
    }

    public static boolean hasSession() {
        return sessionToken != null && !sessionToken.isEmpty();
    }

    public static String getConfigPath() {
        return configPath != null ? configPath.toString() : "config/hypixelai.properties";
    }
}
