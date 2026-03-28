package com.hypixelai;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Config for the HypixelAI mod.
 * Stored at .minecraft/config/hypixelai.properties
 */
public class HypixelAIConfig {

    private static final String API_BASE = "https://sky-ai.uk";

    // Auth
    private static String licenseKey = "";
    private static String sessionToken = "";

    // Toggleable settings
    private static boolean cortisolBar = true;
    private static boolean hideHearts = true;
    private static boolean hideArmor = true;
    private static boolean hideActionBar = true;
    private static boolean overlay = true;
    private static boolean autoUpdate = true;

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
                            case "cortisol_bar" -> cortisolBar = value.equals("true");
                            case "hide_hearts" -> hideHearts = value.equals("true");
                            case "hide_armor" -> hideArmor = value.equals("true");
                            case "hide_action_bar" -> hideActionBar = value.equals("true");
                            case "overlay" -> overlay = value.equals("true");
                            case "auto_update" -> autoUpdate = value.equals("true");
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
            String content = "# HypixelAI Mod Configuration\n"
                    + "license_key=" + licenseKey + "\n"
                    + "session_token=" + sessionToken + "\n"
                    + "\n# Display Settings\n"
                    + "cortisol_bar=" + cortisolBar + "\n"
                    + "hide_hearts=" + hideHearts + "\n"
                    + "hide_armor=" + hideArmor + "\n"
                    + "hide_action_bar=" + hideActionBar + "\n"
                    + "overlay=" + overlay + "\n"
                    + "auto_update=" + autoUpdate + "\n";

            Files.writeString(configPath, content, StandardCharsets.UTF_8);
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to save config", e);
        }
    }

    // Auth getters/setters
    public static String getApiUrl() { return API_BASE + "/api/ask"; }
    public static String getActivateUrl() { return API_BASE + "/api/activate"; }
    public static String getBaseUrl() { return API_BASE; }
    public static String getLicenseKey() { return licenseKey; }
    public static void setLicenseKey(String key) { licenseKey = key; save(); }
    public static String getSessionToken() { return sessionToken; }
    public static void setSessionToken(String token) { sessionToken = token; save(); }
    public static boolean hasSession() { return sessionToken != null && !sessionToken.isEmpty(); }
    public static String getConfigPath() { return configPath != null ? configPath.toString() : "config/hypixelai.properties"; }

    // Toggle getters
    public static boolean isCortisolBar() { return cortisolBar; }
    public static boolean isHideHearts() { return hideHearts; }
    public static boolean isHideArmor() { return hideArmor; }
    public static boolean isHideActionBar() { return hideActionBar; }
    public static boolean isOverlay() { return overlay; }
    public static boolean isAutoUpdate() { return autoUpdate; }

    // Toggle a setting by name. Returns the new value or null if not found.
    public static Boolean toggle(String setting) {
        switch (setting.toLowerCase()) {
            case "cortisol", "cortisol_bar", "cortisolbar" -> { cortisolBar = !cortisolBar; save(); return cortisolBar; }
            case "hearts", "hide_hearts", "hidehearts" -> { hideHearts = !hideHearts; save(); return hideHearts; }
            case "armor", "hide_armor", "hidearmor" -> { hideArmor = !hideArmor; save(); return hideArmor; }
            case "actionbar", "hide_action_bar", "hideactionbar" -> { hideActionBar = !hideActionBar; save(); return hideActionBar; }
            case "overlay", "hud" -> { overlay = !overlay; save(); return overlay; }
            case "autoupdate", "auto_update", "update" -> { autoUpdate = !autoUpdate; save(); return autoUpdate; }
            default -> { return null; }
        }
    }

    // Get all settings as a formatted list
    public static String[][] getAllSettings() {
        return new String[][] {
            {"cortisol", cortisolBar ? "ON" : "OFF", "Cortisol stress gauge"},
            {"hearts", hideHearts ? "ON" : "OFF", "Hide vanilla hearts"},
            {"armor", hideArmor ? "ON" : "OFF", "Hide armor bar"},
            {"actionbar", hideActionBar ? "ON" : "OFF", "Hide SkyBlock action bar"},
            {"overlay", overlay ? "ON" : "OFF", "AI response overlay"},
            {"autoupdate", autoUpdate ? "ON" : "OFF", "Auto-update checking"},
        };
    }
}
