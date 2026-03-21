package com.hypixelai;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Simple config file for the HypixelAI mod.
 * Stored at .minecraft/config/hypixelai.properties
 *
 * On startup, fetches the latest API URL from GitHub so the server
 * can change its URL without pushing a mod update.
 */
public class HypixelAIConfig {

    private static final String DEFAULT_URL = "https://literate-totally-civet.ngrok-free.app/api/ask";
    private static final String REMOTE_CONFIG_URL =
            "https://raw.githubusercontent.com/Msstarke/hypixel-skyblock-ai-bot/master/fabric-mod/remote-config.txt";

    private static String apiUrl = DEFAULT_URL;
    private static String apiKey = "";
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
                            case "api_url" -> apiUrl = value;
                            case "api_key" -> apiKey = value;
                        }
                    }
                }
                HypixelAIMod.LOGGER.info("[HypixelAI] Config loaded from {}", configPath);
            } else {
                save();
                HypixelAIMod.LOGGER.info("[HypixelAI] Default config created at {}", configPath);
            }

            // Migrate old localhost configs
            if (apiUrl.contains("localhost") || apiUrl.contains("127.0.0.1")) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Migrating old localhost URL to public server");
                apiUrl = DEFAULT_URL;
                save();
            }

            // Fetch remote config in background — lets us change the URL without a mod update
            new Thread(() -> fetchRemoteConfig(), "HypixelAI-RemoteConfig").start();

        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] Failed to load config", e);
        }
    }

    /**
     * Fetch the API URL from a raw GitHub file.
     * Format: just the URL on the first line, e.g.
     *   https://literate-totally-civet.ngrok-free.app/api/ask
     */
    private static void fetchRemoteConfig() {
        try {
            URL url = URI.create(REMOTE_CONFIG_URL).toURL();
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(5000);

            if (conn.getResponseCode() != 200) return;

            StringBuilder sb = new StringBuilder();
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = r.readLine()) != null) {
                    line = line.trim();
                    if (!line.isEmpty() && !line.startsWith("#")) {
                        sb.append(line);
                        break; // only need the first non-comment line
                    }
                }
            }
            conn.disconnect();

            String remoteUrl = sb.toString().trim();
            if (!remoteUrl.isEmpty() && remoteUrl.startsWith("http") && !remoteUrl.equals(apiUrl)) {
                HypixelAIMod.LOGGER.info("[HypixelAI] Remote config updated URL: {}", remoteUrl);
                apiUrl = remoteUrl;
                save();
            }
        } catch (Exception e) {
            // Silent fail — remote config is optional
        }
    }

    private static void save() {
        try {
            String content = """
                    # HypixelAI Mod Configuration
                    # api_url is auto-managed. Only change if you run your own server.
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
