package com.hypixelai;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.text.MutableText;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class HypixelAIClient implements ClientModInitializer {

    private static long lastRequest = 0;
    private static final long COOLDOWN_MS = 3000;

    @Override
    public void onInitializeClient() {
        // Load config
        HypixelAIConfig.load();

        // Intercept outgoing chat messages
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            if (message.toLowerCase().startsWith("!ai ")) {
                String question = message.substring(4).trim();
                handleQuestion(question);
                return false; // cancel the chat message
            }
            if (message.toLowerCase().equals("!aihelp")) {
                showHelp();
                return false;
            }
            if (message.toLowerCase().equals("!aiconfig")) {
                showConfig();
                return false;
            }
            return true; // allow normal messages
        });

        HypixelAIMod.LOGGER.info("[HypixelAI] Client mod loaded. Type !ai <question> in chat.");
    }

    private void handleQuestion(String question) {
        if (question.isEmpty()) {
            sendChat(prefix().append(Text.literal("Usage: !ai <question>").formatted(Formatting.GRAY)));
            return;
        }

        // Cooldown
        long now = System.currentTimeMillis();
        if (now - lastRequest < COOLDOWN_MS) {
            sendChat(errorPrefix().append(Text.literal("Wait a moment between questions.").formatted(Formatting.RED)));
            return;
        }
        lastRequest = now;

        sendChat(prefix().append(Text.literal("Thinking...").formatted(Formatting.GRAY)));

        // Run API call on a separate thread to not freeze the game
        String username = getUsername();
        new Thread(() -> {
            try {
                String response = callAPI(question, username);
                if (response != null) {
                    displayResponse(question, response);
                }
            } catch (Exception e) {
                HypixelAIMod.LOGGER.error("[HypixelAI] API call failed", e);
                sendChat(errorPrefix().append(Text.literal("Error: " + e.getMessage()).formatted(Formatting.RED)));
            }
        }, "HypixelAI-API").start();
    }

    private String callAPI(String question, String username) throws Exception {
        String apiUrl = HypixelAIConfig.getApiUrl();
        String apiKey = HypixelAIConfig.getApiKey();

        URL url = URI.create(apiUrl).toURL();
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        conn.setDoOutput(true);
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(30000);

        // Build JSON payload manually (no external JSON lib needed)
        String payload = "{\"question\":" + jsonEscape(question)
                + ",\"api_key\":" + jsonEscape(apiKey)
                + ",\"username\":" + jsonEscape(username) + "}";

        try (OutputStream os = conn.getOutputStream()) {
            os.write(payload.getBytes(StandardCharsets.UTF_8));
        }

        int code = conn.getResponseCode();

        if (code == 200) {
            String body = readStream(conn.getInputStream());
            // Parse chat_lines from JSON response
            return body;
        } else if (code == 401) {
            sendChat(errorPrefix().append(Text.literal("Invalid API key. Check config.").formatted(Formatting.RED)));
        } else if (code == 503) {
            sendChat(errorPrefix().append(Text.literal("Bot is starting up, try again.").formatted(Formatting.RED)));
        } else {
            sendChat(errorPrefix().append(Text.literal("HTTP error " + code).formatted(Formatting.RED)));
        }

        conn.disconnect();
        return null;
    }

    private void displayResponse(String question, String jsonBody) {
        // Parse chat_lines array from JSON
        String[] lines = parseChatLines(jsonBody);
        if (lines.length == 0) {
            sendChat(errorPrefix().append(Text.literal("Empty response.").formatted(Formatting.RED)));
            return;
        }

        // Header
        sendChat(Text.literal("----------------------------------------").formatted(Formatting.GOLD, Formatting.STRIKETHROUGH));
        sendChat(prefix().append(Text.literal(question).formatted(Formatting.YELLOW)));
        sendChat(Text.empty());

        // Response lines
        for (String line : lines) {
            MutableText text;
            if (line.startsWith("- ") || line.startsWith("* ")) {
                text = Text.literal("  " + line).formatted(Formatting.AQUA);
            } else if (line.matches("^\\d+\\..*")) {
                text = Text.literal("  " + line).formatted(Formatting.GREEN);
            } else {
                text = Text.literal("  " + line).formatted(Formatting.WHITE);
            }
            sendChat(text);
        }

        // Footer
        sendChat(Text.literal("----------------------------------------").formatted(Formatting.GOLD, Formatting.STRIKETHROUGH));
    }

    private void showHelp() {
        sendChat(Text.literal("----------------------------------------").formatted(Formatting.GOLD, Formatting.STRIKETHROUGH));
        sendChat(prefix().append(Text.literal("In-Game Commands:").formatted(Formatting.YELLOW)));
        sendChat(Text.literal("  !ai <question>").formatted(Formatting.AQUA)
                .append(Text.literal(" - Ask anything about Skyblock").formatted(Formatting.GRAY)));
        sendChat(Text.literal("  !aihelp").formatted(Formatting.AQUA)
                .append(Text.literal(" - Show this help").formatted(Formatting.GRAY)));
        sendChat(Text.literal("  !aiconfig").formatted(Formatting.AQUA)
                .append(Text.literal(" - Show current config").formatted(Formatting.GRAY)));
        sendChat(Text.empty());
        sendChat(Text.literal("  Examples:").formatted(Formatting.GRAY));
        sendChat(Text.literal("  !ai best money making method").formatted(Formatting.WHITE));
        sendChat(Text.literal("  !ai what pet for mining").formatted(Formatting.WHITE));
        sendChat(Text.literal("  !ai what should i upgrade next").formatted(Formatting.WHITE));
        sendChat(Text.literal("----------------------------------------").formatted(Formatting.GOLD, Formatting.STRIKETHROUGH));
    }

    private void showConfig() {
        sendChat(prefix().append(Text.literal("Config:").formatted(Formatting.YELLOW)));
        sendChat(Text.literal("  API URL: ").formatted(Formatting.GRAY)
                .append(Text.literal(HypixelAIConfig.getApiUrl()).formatted(Formatting.WHITE)));
        sendChat(Text.literal("  API Key: ").formatted(Formatting.GRAY)
                .append(Text.literal(HypixelAIConfig.getApiKey().isEmpty() ? "(none)" : "(set)").formatted(Formatting.WHITE)));
        sendChat(Text.literal("  Config file: ").formatted(Formatting.GRAY)
                .append(Text.literal(HypixelAIConfig.getConfigPath()).formatted(Formatting.WHITE)));
    }

    // --- Utilities ---

    private static MutableText prefix() {
        return Text.literal("[").formatted(Formatting.GOLD)
                .append(Text.literal("SkyAI").formatted(Formatting.AQUA))
                .append(Text.literal("] ").formatted(Formatting.GOLD));
    }

    private static MutableText errorPrefix() {
        return Text.literal("[").formatted(Formatting.GOLD)
                .append(Text.literal("SkyAI").formatted(Formatting.AQUA))
                .append(Text.literal("] ").formatted(Formatting.GOLD));
    }

    private static void sendChat(Text text) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.inGameHud != null) {
            client.execute(() -> client.inGameHud.getChatHud().addMessage(text));
        }
    }

    private static String getUsername() {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client != null && client.getSession() != null) {
            return client.getSession().getUsername();
        }
        return "";
    }

    private static String readStream(InputStream is) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private static String jsonEscape(String s) {
        if (s == null) return "\"\"";
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default: sb.append(c);
            }
        }
        sb.append("\"");
        return sb.toString();
    }

    /**
     * Parse the "chat_lines" array from the JSON response.
     * Minimal JSON parsing — no external library needed.
     */
    private static String[] parseChatLines(String json) {
        // Find "chat_lines": [...]
        int idx = json.indexOf("\"chat_lines\"");
        if (idx == -1) return new String[0];

        int arrStart = json.indexOf('[', idx);
        if (arrStart == -1) return new String[0];

        int arrEnd = json.indexOf(']', arrStart);
        if (arrEnd == -1) return new String[0];

        String arrContent = json.substring(arrStart + 1, arrEnd);
        if (arrContent.trim().isEmpty()) return new String[0];

        // Split by ","  but respect escaped quotes
        java.util.List<String> lines = new java.util.ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inString = false;
        boolean escaped = false;

        for (int i = 0; i < arrContent.length(); i++) {
            char c = arrContent.charAt(i);

            if (escaped) {
                if (c == 'n') current.append('\n');
                else if (c == 't') current.append('\t');
                else current.append(c);
                escaped = false;
                continue;
            }

            if (c == '\\') {
                escaped = true;
                continue;
            }

            if (c == '"') {
                inString = !inString;
                continue;
            }

            if (c == ',' && !inString) {
                String line = current.toString().trim();
                if (!line.isEmpty()) lines.add(line);
                current = new StringBuilder();
                continue;
            }

            if (inString) {
                current.append(c);
            }
        }

        String last = current.toString().trim();
        if (!last.isEmpty()) lines.add(last);

        return lines.toArray(new String[0]);
    }
}
