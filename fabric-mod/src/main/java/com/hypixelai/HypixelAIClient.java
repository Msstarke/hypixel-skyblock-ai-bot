package com.hypixelai;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.text.MutableText;
import net.minecraft.text.Style;
import net.minecraft.text.Text;
import net.minecraft.text.HoverEvent;
import net.minecraft.text.ClickEvent;
import net.minecraft.util.Formatting;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class HypixelAIClient implements ClientModInitializer {

    private static long lastRequest = 0;
    private static final long COOLDOWN_MS = 3000;

    // Color scheme
    private static final Formatting ACCENT = Formatting.GOLD;
    private static final Formatting BRAND = Formatting.AQUA;
    private static final Formatting BODY = Formatting.GRAY;
    private static final Formatting HIGHLIGHT = Formatting.WHITE;
    private static final Formatting SUCCESS = Formatting.GREEN;
    private static final Formatting ERROR = Formatting.RED;
    private static final Formatting MUTED = Formatting.DARK_GRAY;

    @Override
    public void onInitializeClient() {
        HypixelAIConfig.load();

        // Check for updates in background
        new Thread(() -> HypixelAIUpdater.checkForUpdate(), "HypixelAI-Updater").start();

        // Show update message when player joins a world
        final boolean[] notified = {false};
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            if (!notified[0] && client.player != null && HypixelAIUpdater.isUpdatePending()) {
                notified[0] = true;
                sendChat(Text.empty());
                sendChat(prefix()
                        .append(Text.literal("Update available! ").styled(s -> s.withColor(Formatting.GREEN)))
                        .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED))
                        .append(Text.literal(" \u2192 ").formatted(MUTED))
                        .append(Text.literal("v" + HypixelAIUpdater.getPendingVersion()).formatted(SUCCESS, Formatting.BOLD)));
                String msg = HypixelAIUpdater.getUpdateMessage();
                if (msg != null && !msg.isEmpty()) {
                    sendChat(Text.literal("   " + msg).formatted(BODY));
                }
                sendChat(Text.literal("   Restart your game to apply.").formatted(MUTED));
                sendChat(Text.empty());
            }
        });

        // Intercept outgoing chat messages
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            String lower = message.toLowerCase();

            if (lower.startsWith("!ai ")) {
                handleQuestion(message.substring(4).trim());
                return false;
            }
            if (lower.equals("!ai")) {
                showHelp();
                return false;
            }
            if (lower.equals("!aihelp")) {
                showHelp();
                return false;
            }
            if (lower.equals("!aiconfig")) {
                showConfig();
                return false;
            }
            if (lower.startsWith("!link ")) {
                handleLink(message.substring(6).trim());
                return false;
            }
            if (lower.equals("!link")) {
                sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                        .append(Text.literal("!link <ign>").formatted(HIGHLIGHT)));
                return false;
            }
            if (lower.equals("!unlink")) {
                handleUnlink();
                return false;
            }
            return true;
        });

        HypixelAIMod.LOGGER.info("[HypixelAI] Client mod loaded v{}", HypixelAIUpdater.MOD_VERSION);
    }

    private void handleLink(String ign) {
        if (ign.isEmpty()) {
            sendChat(prefix().append(Text.literal("Usage: ").formatted(BODY))
                    .append(Text.literal("!link <ign>").formatted(HIGHLIGHT)));
            return;
        }

        String username = getUsername();
        sendChat(prefix().append(Text.literal("Linking to ").formatted(BODY))
                .append(Text.literal(ign).formatted(BRAND))
                .append(Text.literal("...").formatted(BODY)));

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getApiUrl().replace("/api/ask", "");
                String payload = "{\"username\":" + jsonEscape(username)
                        + ",\"ign\":" + jsonEscape(ign)
                        + ",\"api_key\":" + jsonEscape(HypixelAIConfig.getApiKey()) + "}";

                URL url = URI.create(baseUrl + "/api/link").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setRequestProperty("ngrok-skip-browser-warning", "true");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                int code = conn.getResponseCode();
                conn.disconnect();

                if (code == 200) {
                    sendChat(prefix().append(Text.literal("\u2714 ").formatted(SUCCESS))
                            .append(Text.literal("Linked to ").formatted(BODY))
                            .append(Text.literal(ign).formatted(BRAND))
                            .append(Text.literal(" \u2014 responses are now personalized.").formatted(BODY)));
                } else {
                    sendChat(prefix().append(Text.literal("\u2716 Failed to link ").formatted(ERROR))
                            .append(Text.literal("(HTTP " + code + ")").formatted(MUTED)));
                }
            } catch (Exception e) {
                sendChat(prefix().append(Text.literal("\u2716 Link failed: ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }, "HypixelAI-Link").start();
    }

    private void handleUnlink() {
        String username = getUsername();

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getApiUrl().replace("/api/ask", "");
                String payload = "{\"username\":" + jsonEscape(username)
                        + ",\"api_key\":" + jsonEscape(HypixelAIConfig.getApiKey()) + "}";

                URL url = URI.create(baseUrl + "/api/unlink").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setRequestProperty("ngrok-skip-browser-warning", "true");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                int code = conn.getResponseCode();
                conn.disconnect();

                if (code == 200) {
                    sendChat(prefix().append(Text.literal("\u2714 Unlinked.").formatted(Formatting.YELLOW)));
                } else {
                    sendChat(prefix().append(Text.literal("\u2716 Failed to unlink ").formatted(ERROR))
                            .append(Text.literal("(HTTP " + code + ")").formatted(MUTED)));
                }
            } catch (Exception e) {
                sendChat(prefix().append(Text.literal("\u2716 Unlink failed: ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
            }
        }, "HypixelAI-Unlink").start();
    }

    private void handleQuestion(String question) {
        if (question.isEmpty()) {
            showHelp();
            return;
        }

        // Cooldown
        long now = System.currentTimeMillis();
        if (now - lastRequest < COOLDOWN_MS) {
            sendChat(prefix().append(Text.literal("Slow down! Wait a moment.").formatted(Formatting.YELLOW)));
            return;
        }
        lastRequest = now;

        sendChat(prefix().append(Text.literal("\u231B Thinking...").formatted(MUTED)));

        String username = getUsername();
        new Thread(() -> {
            try {
                String response = callAPI(question, username);
                if (response != null) {
                    displayResponse(question, response);
                }
            } catch (Exception e) {
                HypixelAIMod.LOGGER.error("[HypixelAI] API call failed", e);
                sendChat(prefix().append(Text.literal("\u2716 ").formatted(ERROR))
                        .append(Text.literal(e.getMessage()).formatted(MUTED)));
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
        conn.setRequestProperty("ngrok-skip-browser-warning", "true");
        conn.setDoOutput(true);
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(30000);

        String payload = "{\"question\":" + jsonEscape(question)
                + ",\"api_key\":" + jsonEscape(apiKey)
                + ",\"username\":" + jsonEscape(username) + "}";

        try (OutputStream os = conn.getOutputStream()) {
            os.write(payload.getBytes(StandardCharsets.UTF_8));
        }

        int code = conn.getResponseCode();

        if (code == 200) {
            return readStream(conn.getInputStream());
        } else if (code == 401) {
            sendChat(prefix().append(Text.literal("\u2716 Invalid API key.").formatted(ERROR)));
        } else if (code == 503) {
            sendChat(prefix().append(Text.literal("\u231B Bot is starting up, try again.").formatted(Formatting.YELLOW)));
        } else {
            sendChat(prefix().append(Text.literal("\u2716 HTTP " + code).formatted(ERROR)));
        }

        conn.disconnect();
        return null;
    }

    private void displayResponse(String question, String jsonBody) {
        String[] lines = parseChatLines(jsonBody);
        if (lines.length == 0) {
            sendChat(prefix().append(Text.literal("No response.").formatted(MUTED)));
            return;
        }

        // Top bar
        sendChat(divider());

        // Question echo
        sendChat(prefix()
                .append(Text.literal(question).formatted(HIGHLIGHT, Formatting.BOLD)));

        // Response lines
        for (String line : lines) {
            MutableText text;
            if (line.startsWith("- ") || line.startsWith("* ")) {
                // Bullet point: replace dash with a dot symbol
                String content = line.substring(2);
                text = Text.literal("  \u2022 ").formatted(ACCENT)
                        .append(Text.literal(content).formatted(BODY));
            } else if (line.matches("^\\d+\\.\\s.*")) {
                // Numbered list: highlight the number
                int dotIdx = line.indexOf('.');
                String num = line.substring(0, dotIdx + 1);
                String content = line.substring(dotIdx + 1).trim();
                text = Text.literal("  " + num + " ").formatted(ACCENT)
                        .append(Text.literal(content).formatted(BODY));
            } else {
                text = Text.literal("  " + line).formatted(BODY);
            }
            sendChat(text);
        }

        // Bottom bar
        sendChat(divider());
    }

    private void showHelp() {
        sendChat(divider());
        sendChat(prefix().append(Text.literal("Commands").formatted(HIGHLIGHT, Formatting.BOLD)));
        sendChat(Text.empty());

        helpLine("!ai <question>", "Ask anything about Skyblock");
        helpLine("!link <ign>", "Link your account for personalized answers");
        helpLine("!unlink", "Remove your linked account");
        helpLine("!aiconfig", "View current mod config");

        sendChat(Text.empty());
        sendChat(Text.literal("  Examples:").formatted(MUTED));
        exampleLine("!ai best money making method");
        exampleLine("!ai what pet for mining");
        exampleLine("!ai what should i upgrade next");
        sendChat(divider());
    }

    private void helpLine(String cmd, String desc) {
        MutableText cmdText = Text.literal("  " + cmd).styled(s -> s
                .withColor(Formatting.AQUA)
                .withHoverEvent(new HoverEvent.ShowText(Text.literal("Click to type").formatted(MUTED)))
                .withClickEvent(new ClickEvent.SuggestCommand(cmd)));
        MutableText descText = Text.literal(" \u2014 " + desc).formatted(MUTED);
        sendChat(cmdText.append(descText));
    }

    private void exampleLine(String example) {
        sendChat(Text.literal("    " + example).styled(s -> s
                .withColor(Formatting.DARK_GRAY)
                .withItalic(true)
                .withHoverEvent(new HoverEvent.ShowText(Text.literal("Click to type").formatted(MUTED)))
                .withClickEvent(new ClickEvent.SuggestCommand(example))));
    }

    private void showConfig() {
        sendChat(divider());
        sendChat(prefix().append(Text.literal("Config").formatted(HIGHLIGHT, Formatting.BOLD)));

        sendChat(Text.literal("  API: ").formatted(MUTED)
                .append(Text.literal(HypixelAIConfig.getApiUrl()).formatted(BODY)));
        sendChat(Text.literal("  Key: ").formatted(MUTED)
                .append(Text.literal(HypixelAIConfig.getApiKey().isEmpty() ? "not set" : "\u2714 set").formatted(
                        HypixelAIConfig.getApiKey().isEmpty() ? Formatting.YELLOW : SUCCESS)));
        sendChat(Text.literal("  Version: ").formatted(MUTED)
                .append(Text.literal("v" + HypixelAIUpdater.MOD_VERSION).formatted(BODY)));

        sendChat(divider());
    }

    // --- Utilities ---

    private static MutableText prefix() {
        return Text.literal("\u2B25 ").formatted(ACCENT)
                .append(Text.literal("SkyAI").styled(s -> s
                        .withColor(Formatting.AQUA)
                        .withBold(true)
                        .withHoverEvent(new HoverEvent.ShowText(
                                Text.literal("HypixelAI v" + HypixelAIUpdater.MOD_VERSION).formatted(MUTED)))))
                .append(Text.literal(" \u00BB ").formatted(MUTED));
    }

    private static MutableText divider() {
        return Text.literal("                                        ").styled(s -> s
                .withColor(Formatting.DARK_GRAY)
                .withStrikethrough(true));
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
     */
    private static String[] parseChatLines(String json) {
        int idx = json.indexOf("\"chat_lines\"");
        if (idx == -1) return new String[0];

        int arrStart = json.indexOf('[', idx);
        if (arrStart == -1) return new String[0];

        int arrEnd = json.indexOf(']', arrStart);
        if (arrEnd == -1) return new String[0];

        String arrContent = json.substring(arrStart + 1, arrEnd);
        if (arrContent.trim().isEmpty()) return new String[0];

        java.util.List<String> lines = new java.util.ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inString = false;
        boolean escaped = false;

        for (int i = 0; i < arrContent.length(); i++) {
            char c = arrContent.charAt(i);

            if (escaped) {
                if (c == 'n') current.append('\n');
                else if (c == 't') current.append('\t');
                else if (c == 'u' && i + 4 < arrContent.length()) {
                    String hex = arrContent.substring(i + 1, i + 5);
                    try {
                        current.append((char) Integer.parseInt(hex, 16));
                        i += 4;
                    } catch (NumberFormatException e) {
                        current.append(c);
                    }
                }
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
