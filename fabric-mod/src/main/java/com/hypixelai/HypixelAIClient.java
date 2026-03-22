package com.hypixelai;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
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

        // Register HUD overlay
        SkyAIOverlay.register();

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
            if (lower.equals("!correct") || lower.equals("!right") || lower.equals("!good")) {
                handleFeedback("up");
                return false;
            }
            if (lower.equals("!wrong") || lower.equals("!bad") || lower.equals("!incorrect")) {
                handleFeedback("down");
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

    private void handleFeedback(String vote) {
        if (!SkyAIOverlay.hasPendingFeedback()) {
            sendChat(prefix().append(Text.literal("No response to rate right now.").formatted(MUTED)));
            return;
        }

        String label = vote.equals("up") ? "\u2714 Correct" : "\u2716 Wrong";
        Formatting color = vote.equals("up") ? SUCCESS : ERROR;
        SkyAIOverlay.setFeedback(vote);
        sendChat(prefix().append(Text.literal("Feedback: ").formatted(BODY))
                .append(Text.literal(label).formatted(color))
                .append(Text.literal(" — thanks!").formatted(BODY)));

        String question = SkyAIOverlay.getLastQuestion();
        String response = SkyAIOverlay.getLastResponse();
        String username = getUsername();

        new Thread(() -> {
            try {
                String baseUrl = HypixelAIConfig.getApiUrl().replace("/api/ask", "");
                String payload = "{\"vote\":" + jsonEscape(vote)
                        + ",\"username\":" + jsonEscape(username)
                        + ",\"question\":" + jsonEscape(question != null ? question : "")
                        + ",\"response\":" + jsonEscape(response != null ? response : "")
                        + ",\"api_key\":" + jsonEscape(HypixelAIConfig.getApiKey()) + "}";

                URL url = URI.create(baseUrl + "/api/feedback").toURL();
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(10000);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(payload.getBytes(StandardCharsets.UTF_8));
                }

                conn.getResponseCode();
                conn.disconnect();
            } catch (Exception e) {
                HypixelAIMod.LOGGER.warn("[HypixelAI] Feedback send failed: {}", e.getMessage());
            }
        }, "HypixelAI-Feedback").start();
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

        SkyAIOverlay.showThinking(question);

        String username = getUsername();
        new Thread(() -> {
            try {
                String response = callAPI(question, username);
                if (response != null) {
                    displayResponse(question, response);
                } else {
                    SkyAIOverlay.clear();
                }
            } catch (Exception e) {
                HypixelAIMod.LOGGER.error("[HypixelAI] API call failed", e);
                SkyAIOverlay.clear();
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
            SkyAIOverlay.clear();
            sendChat(prefix().append(Text.literal("No response.").formatted(MUTED)));
            return;
        }

        // Parse HOTM data if present
        int[] hotmPerks = parseHotmData(jsonBody);

        // Show in the HUD overlay
        SkyAIOverlay.show(question, lines, hotmPerks);
    }

    private void showHelp() {
        String[] helpLines = {
                "Commands:",
                "",
                "- !ai <question>  \u2014  Ask anything about Skyblock",
                "- !link <ign>  \u2014  Link your account",
                "- !unlink  \u2014  Remove linked account",
                "- !correct / !wrong  \u2014  Rate the AI response",
                "- !aiconfig  \u2014  View mod config",
                "",
                "Examples:",
                "",
                "1. !ai best money making method",
                "2. !ai what pet for mining",
                "3. !ai what should i upgrade next",
        };
        SkyAIOverlay.show("Help", helpLines);
    }

    private void showConfig() {
        String keyStatus = HypixelAIConfig.getApiKey().isEmpty() ? "not set" : "set";
        String[] configLines = {
                "API: " + HypixelAIConfig.getApiUrl(),
                "Key: " + keyStatus,
                "Version: v" + HypixelAIUpdater.MOD_VERSION,
                "Config: " + HypixelAIConfig.getConfigPath(),
        };
        SkyAIOverlay.show("Config", configLines);
    }

    // --- Utilities ---

    private static MutableText prefix() {
        return Text.literal("\u2B25 ").formatted(ACCENT)
                .append(Text.literal("SkyAI").formatted(BRAND, Formatting.BOLD))
                .append(Text.literal(" \u00BB ").formatted(MUTED));
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
     * Parse HOTM data from JSON response for pixel art rendering.
     * Returns int[70] (10 tiers x 7 cols) where each value is:
     *   0 = empty (no perk at this position)
     *  -1 = locked (tier above player level)
     *   1 = unlocked but level 0
     *   2 = partially leveled
     *   3 = maxed
     *   4 = ability (unlocked)
     *   5 = ability (selected/active)
     * Returns null if no HOTM data in response.
     */
    private static int[] parseHotmData(String json) {
        int hotmIdx = json.indexOf("\"hotm\"");
        if (hotmIdx == -1) return null;

        // Parse level
        int levelVal = parseIntField(json, "\"level\"", hotmIdx);
        if (levelVal < 0) return null;

        // Parse selected ability
        String selectedAbility = parseStringField(json, "\"selected_ability\"", hotmIdx);

        // Parse perks object
        int perksIdx = json.indexOf("\"perks\"", hotmIdx);
        if (perksIdx == -1) return null;

        // Tree layout: [tier][col] -> api_id
        // Tier 0=tier1(bottom), tier 9=tier10(top)
        String[][] TREE = {
            {null, null, null, "mining_speed", null, null, null},           // T1
            {null, "mining_speed_boost", "precision_mining", "mining_fortune", "titanium_insanium", "pickaxe_toss", null}, // T2
            {null, "random_event", null, "efficient_miner", null, "forge_time", null},  // T3
            {"daily_effect", "old_school", "professional", "mole", "fortunate", "mining_experience", "front_loaded"}, // T4
            {null, "daily_grind", null, "special_0", null, "daily_powder", null},        // T5
            {"anomalous_desire", "blockhead", "subterranean_fisher", "keep_it_cool", "lonesome_miner", "great_explorer", "maniac_miner"}, // T6
            {null, "mining_speed_2", null, "powder_buff", null, "mining_fortune_2", null}, // T7
            {"miners_blessing", "no_stone_unturned", "strong_arm", "steady_hand", "warm_hearted", "surveyor", "mineshaft_mayhem"}, // T8
            {null, "metal_head", null, "rags_to_riches", null, "eager_adventurer", null}, // T9
            {"gemstone_infusion", "crystalline", "gifts_from_the_departed", "mining_master", "hungry_for_more", "vanguard_seeker", "sheer_force"}, // T10
        };

        int[] MAX_LEVELS = {50, 1,1,50,50,1, 45,100,20, 1,20,140,200,20,100,1, 1,10,1, 1,20,40,50,45,20,1, 50,50,50, 1,50,100,100,50,20,1, 20,50,100, 1,50,100,10,50,50,1};

        java.util.Set<String> ABILITIES = new java.util.HashSet<>(java.util.Arrays.asList(
            "mining_speed_boost", "pickaxe_toss", "anomalous_desire", "maniac_miner", "gemstone_infusion", "sheer_force"
        ));

        // Build max level lookup
        java.util.Map<String, Integer> maxLevels = new java.util.HashMap<>();
        maxLevels.put("mining_speed", 50); maxLevels.put("mining_speed_boost", 1); maxLevels.put("precision_mining", 1);
        maxLevels.put("mining_fortune", 50); maxLevels.put("titanium_insanium", 50); maxLevels.put("pickaxe_toss", 1);
        maxLevels.put("random_event", 45); maxLevels.put("efficient_miner", 100); maxLevels.put("forge_time", 20);
        maxLevels.put("daily_effect", 1); maxLevels.put("old_school", 20); maxLevels.put("professional", 140);
        maxLevels.put("mole", 200); maxLevels.put("fortunate", 20); maxLevels.put("mining_experience", 100);
        maxLevels.put("front_loaded", 1); maxLevels.put("daily_grind", 1); maxLevels.put("special_0", 10);
        maxLevels.put("daily_powder", 1); maxLevels.put("anomalous_desire", 1); maxLevels.put("blockhead", 20);
        maxLevels.put("subterranean_fisher", 40); maxLevels.put("keep_it_cool", 50); maxLevels.put("lonesome_miner", 45);
        maxLevels.put("great_explorer", 20); maxLevels.put("maniac_miner", 1); maxLevels.put("mining_speed_2", 50);
        maxLevels.put("powder_buff", 50); maxLevels.put("mining_fortune_2", 50); maxLevels.put("miners_blessing", 1);
        maxLevels.put("no_stone_unturned", 50); maxLevels.put("strong_arm", 100); maxLevels.put("steady_hand", 100);
        maxLevels.put("warm_hearted", 50); maxLevels.put("surveyor", 20); maxLevels.put("mineshaft_mayhem", 1);
        maxLevels.put("metal_head", 20); maxLevels.put("rags_to_riches", 50); maxLevels.put("eager_adventurer", 100);
        maxLevels.put("gemstone_infusion", 1); maxLevels.put("crystalline", 50); maxLevels.put("gifts_from_the_departed", 100);
        maxLevels.put("mining_master", 10); maxLevels.put("hungry_for_more", 50); maxLevels.put("vanguard_seeker", 50);
        maxLevels.put("sheer_force", 1);

        int[] grid = new int[70]; // 10 tiers x 7 cols

        for (int tier = 0; tier < 10; tier++) {
            boolean locked = (tier + 1) > levelVal;
            for (int col = 0; col < 7; col++) {
                String perkId = TREE[tier][col];
                int idx = tier * 7 + col;
                if (perkId == null) {
                    grid[idx] = 0; // empty
                } else if (locked) {
                    grid[idx] = -1; // locked
                } else {
                    int perkLevel = parseIntField(json, "\"" + perkId + "\"", perksIdx);
                    if (perkLevel < 0) perkLevel = 0;
                    boolean isAbility = ABILITIES.contains(perkId);
                    int maxLvl = maxLevels.getOrDefault(perkId, 1);

                    if (isAbility && perkLevel > 0) {
                        grid[idx] = (perkId.equals(selectedAbility)) ? 5 : 4;
                    } else if (perkLevel >= maxLvl && perkLevel > 0) {
                        grid[idx] = 3; // maxed
                    } else if (perkLevel > 0) {
                        grid[idx] = 2; // partial
                    } else {
                        grid[idx] = 1; // unlocked, 0
                    }
                }
            }
        }
        return grid;
    }

    private static int parseIntField(String json, String key, int searchFrom) {
        int idx = json.indexOf(key, searchFrom);
        if (idx == -1) return -1;
        int colon = json.indexOf(':', idx + key.length());
        if (colon == -1) return -1;
        // Find the number
        int start = colon + 1;
        while (start < json.length() && (json.charAt(start) == ' ' || json.charAt(start) == '"')) start++;
        int end = start;
        while (end < json.length() && (Character.isDigit(json.charAt(end)) || json.charAt(end) == '.')) end++;
        if (end == start) return -1;
        try {
            return (int) Double.parseDouble(json.substring(start, end));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static String parseStringField(String json, String key, int searchFrom) {
        int idx = json.indexOf(key, searchFrom);
        if (idx == -1) return "";
        int colon = json.indexOf(':', idx + key.length());
        if (colon == -1) return "";
        int qStart = json.indexOf('"', colon + 1);
        if (qStart == -1) return "";
        int qEnd = json.indexOf('"', qStart + 1);
        if (qEnd == -1) return "";
        return json.substring(qStart + 1, qEnd);
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
